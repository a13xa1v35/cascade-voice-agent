"""Full-Duplex-Bench inference CLI.

uv run python -m evals.turn_taking.run --config evals/turn_taking/configs/baseline.yaml [--limit N]
    [--only v1/candor_pause_handling] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from loguru import logger

from evals.turn_taking.agent import make_bench_agent
from evals.turn_taking.config import (
    BenchConfig,
    agent_resolved,
    build_manifest,
    load_config,
    resolve_settings,
    select_samples,
    write_manifest,
)
from evals.turn_taking.session import SessionUnhealthy, run_session
from evals.turn_taking.throttle import StartThrottle, with_retries
from evals.turn_taking.variants import VARIANTS, missing_variant_keys
from evals.turn_taking.wav_transport import wav_duration_secs
from hr_screener.config import Settings
from hr_screener.pipeline.providers import require_keys

RUNS_DIR = Path("evals/results/turn_taking")
# Files we produce; never symlinked (the source folder may hold same-named files).
OUTPUT_NAMES = {
    "output.wav",
    "clean_output.wav",
    "events.json",
    "clean_events.json",
    "bot.log",
    "clean_bot.log",
}


def filter_samples(
    samples: list[dict[str, str]], only: str | None, limit: int | None
) -> list[dict[str, str]]:
    if only:
        samples = [s for s in samples if f"{s['version']}/{s['task']}" == only]
    return samples[:limit] if limit else samples


def sample_key(s: dict[str, str]) -> str:
    return f"{s['version']}/{s['task']}/{s['id']}"


def _jobs(s: dict[str, str], cfg: BenchConfig) -> list[tuple[str, str, str, str]]:
    """(input name, output name, events name, log name) for the main and clean sessions."""
    jobs = [("input.wav", "output.wav", "events.json", "bot.log")]
    if (
        cfg.run.clean_inputs
        and s["version"] == "v1.5"
        and (Path(s["source"]) / "clean_input.wav").exists()
    ):
        jobs.append(("clean_input.wav", "clean_output.wav", "clean_events.json", "clean_bot.log"))
    return jobs


def print_plan(cfg: BenchConfig, samples: list[dict[str, str]], resolved: dict[str, str]) -> float:
    print("Agent (resolved from env_file + overrides, language forced to en):")
    for k, v in resolved.items():
        print(f"  {k}: {v}")
    per_task: dict[str, list[float]] = {}
    total = 0.0
    for s in samples:
        for in_name, *_ in _jobs(s, cfg):
            d = wav_duration_secs(Path(s["source"]) / in_name)
            per_task.setdefault(f"{s['version']}/{s['task']}", []).append(d)
            total += d + cfg.run.trailing_silence_secs + 1.0
    print(f"Selection: {len(samples)} samples")
    for task, ds in per_task.items():
        print(f"  {task}: {len(ds)} sessions, {sum(ds):.0f}s audio")
    sessions = sum(len(ds) for ds in per_task.values())
    audio_bound = total / cfg.run.concurrency
    rate_bound = sessions / cfg.run.max_session_starts_per_minute * 60
    est = max(audio_bound, rate_bound)
    print(
        f"Total input audio incl. clean runs: {sum(sum(d) for d in per_task.values()):.0f}s, "
        f"{sessions} sessions\n"
        f"estimated wall time ~{est / 60:.1f} min = max(audio-bound {audio_bound / 60:.1f} min "
        f"at concurrency {cfg.run.concurrency}, start-rate-bound {rate_bound / 60:.1f} min at "
        f"{cfg.run.max_session_starts_per_minute} session starts/min)"
    )
    return est


def prepare_sample_dir(run_dir: Path, s: dict[str, str]) -> Path:
    out = run_dir / s["version"] / s["task"] / s["id"]
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(s["source"]).iterdir()):
        if f.name in OUTPUT_NAMES:
            continue
        link = out / f.name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(f.resolve())
    return out


async def run_one(
    s: dict[str, str],
    cfg: BenchConfig,
    settings: Settings,
    run_dir: Path,
    throttle: StartThrottle,
    variant_params: Mapping[str, Any] | None = None,
) -> list[str]:
    variant = VARIANTS[cfg.agent.variant]
    agent = make_bench_agent(
        tool_latency_secs=cfg.run.tool_latency_secs,
        extra_instructions=variant.extra_instructions,
    )
    out = prepare_sample_dir(run_dir, s)
    done = []
    for in_name, out_name, ev_name, log_name in _jobs(s, cfg):
        if (
            cfg.run.skip_existing
            and (out / out_name).is_file()
            and not (out / out_name).is_symlink()
        ):
            done.append(f"{out_name}(skipped)")
            continue
        tag = f"{sample_key(s)}:{in_name}"
        sink = logger.add(
            out / log_name,
            level="DEBUG",
            filter=lambda r, tag=tag: r["extra"].get("bench_job") == tag,
        )

        async def attempt(in_name=in_name, out_name=out_name, ev_name=ev_name, tag=tag):
            with logger.contextualize(bench_job=tag):
                return await run_session(
                    builder=variant.build,
                    settings=settings,
                    agent=agent,
                    telephony=cfg.agent.audio_profile == "telephony",
                    input_wav=Path(s["source"]) / in_name,
                    output_wav=out / out_name,
                    events_path=out / ev_name,
                    trailing_silence_secs=cfg.run.trailing_silence_secs,
                    before_start=throttle.acquire,
                    variant_params=variant_params
                    or variant.resolve_params(cfg.agent.variant_params, design=cfg.agent.design),
                )

        def on_retry(n: int, e: Exception, tag=tag) -> None:
            print(
                f"  {tag} rate limited ({e}); retry {n}/{cfg.run.max_retries} "
                f"in {cfg.run.retry_wait_secs:.0f}s",
                flush=True,
            )

        try:
            stats = await with_retries(
                attempt,
                should_retry=lambda e: isinstance(e, SessionUnhealthy) and e.rate_limited,
                max_retries=cfg.run.max_retries,
                wait_secs=cfg.run.retry_wait_secs,
                on_retry=on_retry,
            )
            done.append(f"{out_name} speech={stats['speech_secs']:.1f}s")
        finally:
            logger.remove(sink)
    return done


async def run_batch(
    cfg: BenchConfig,
    settings: Settings,
    samples: list[dict[str, str]],
    run_dir: Path,
    variant_params: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    sem = asyncio.Semaphore(cfg.run.concurrency)
    throttle = StartThrottle(cfg.run.max_session_starts_per_minute)
    failures: list[dict[str, str]] = []
    counter = {"n": 0}
    t_start = time.monotonic()

    async def work(s: dict[str, str]) -> None:
        async with sem:
            t = time.monotonic()
            try:
                done = await run_one(s, cfg, settings, run_dir, throttle, variant_params)
                status = "ok " + ", ".join(done)
            except Exception as e:
                failures.append(
                    {"sample": sample_key(s), "error": repr(e), "traceback": traceback.format_exc()}
                )
                status = f"FAILED {e!r}"
            counter["n"] += 1
            print(
                f"[{counter['n']}/{len(samples)}] {sample_key(s)} {status} "
                f"({time.monotonic() - t:.0f}s, total {time.monotonic() - t_start:.0f}s)",
                flush=True,
            )

    await asyncio.gather(*(work(s) for s in samples))
    (run_dir / "failures.json").write_text(json.dumps(failures, indent=1))
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Full-Duplex-Bench inference")
    ap.add_argument("--config", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", help="restrict to one task, e.g. v1/candor_pause_handling")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--fake-classifier",
        action="store_true",
        help="system_one only: use an offline heuristic instead of Clef (no Cloudflare calls)",
    )
    ap.add_argument("--runs-dir", default=str(RUNS_DIR))
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if cfg.agent.variant not in VARIANTS:
        sys.exit(f"unknown variant {cfg.agent.variant!r}; known: {sorted(VARIANTS)}")
    if args.fake_classifier and cfg.agent.variant != "system_one":
        sys.exit("--fake-classifier only applies to the system_one variant")
    settings = resolve_settings(cfg)
    if settings.llm_provider != "anthropic":
        # The bench agent is fixed so runs measure the turn-taking design; the manifest and the
        # cost section record and price an Anthropic model (every committed report is one).
        sys.exit(
            f"the turn-taking eval runs Sofia's LLM on Anthropic; got LLM_PROVIDER="
            f"{settings.llm_provider!r} (set LLM_PROVIDER=anthropic in the env_file)"
        )
    resolved = agent_resolved(cfg, settings, fake_classifier=args.fake_classifier)
    variant_params = VARIANTS[cfg.agent.variant].resolve_params(
        cfg.agent.variant_params, design=cfg.agent.design, fake_classifier=args.fake_classifier
    )
    samples = filter_samples(select_samples(cfg), args.only, args.limit)
    if not samples:
        sys.exit("no samples selected")
    print_plan(cfg, samples, resolved)
    if missing := missing_variant_keys(VARIANTS[cfg.agent.variant], settings, variant_params):
        message = (
            f"variant {cfg.agent.variant!r} needs {', '.join(missing)} (set them in the env_file)"
        )
        if not args.dry_run:
            sys.exit(message)
        print(f"WARNING: {message}")
    if args.dry_run:
        for s in samples:
            print(f"  {sample_key(s)}  <- {s['source']}")
        return 0

    require_keys(settings, turn_model=False)  # the variant's own keys were checked above
    # Pipecat's own logs are noisy; keep the console quiet, per-sample sinks capture detail.
    logger.remove()
    run_dir = Path(args.runs_dir) / cfg.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(run_dir / "manifest.json", build_manifest(cfg, samples, resolved))
    failures = asyncio.run(run_batch(cfg, settings, samples, run_dir, variant_params))
    ok = len(samples) - len(failures)
    msg = f"{ok} ok, {len(failures)} failed"
    if failures:
        msg += " \u2014 rerun the same command to retry the failed ones"
    print(f"{msg} -> {run_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
