"""Eval CLI.

    uv run python -m evals.e2e.run --scenarios a,c --langs es,en --runs 3
    make eval-e2e SCENARIOS=c,l2 LANGS=es RUNS=1
    uv run python -m evals.e2e.run --scenarios k1,k2,k3,k4,k5,k6,k7,k8 --langs es,en \\
        --kb-provider local        # knowledge scenarios; local needs no API key

Each invocation writes `evals/results/e2e/<timestamp>/` (report.md, runs.jsonl, one SQLite file
per conversation, per-call logs) and uses EVAL_REDIS_URL (default redis://localhost:6379/15)
for the event timelines, deleting the keys it created. It never touches DATABASE_URL or
REDIS_URL. Real API calls are made: Sofia, the simulated candidate, the post-call summary and
the judge. See evals/e2e/README.md.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from loguru import logger
from redis.asyncio import Redis

from evals.e2e.harness import Conversation, EvalConfig
from evals.e2e.kb import KbHub
from evals.e2e.records import RunRecord
from evals.e2e.report import ReportMeta, default_models, render_report
from evals.e2e.scenarios import SCENARIOS
from evals.kb.embed_cache import DEFAULT_CACHE_DIR
from hr_screener.config import Settings
from hr_screener.knowledge.types import KnowledgeError
from hr_screener.pipeline.providers import missing_keys

DEFAULT_REDIS_URL = "redis://localhost:6379/15"
RESULTS_ROOT = Path(__file__).parent.parent / "results" / "e2e"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scenarios", default="all", help="comma-separated ids, or 'all'")
    parser.add_argument("--langs", default="es", help="call languages: es,en")
    parser.add_argument("--runs", type=int, default=1, help="conversations per scenario x language")
    parser.add_argument("--no-summary", action="store_true", help="skip the post-call summary")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--kb-provider",
        choices=["openai", "voyage", "local"],
        help="embeddings of the knowledge-base scenarios (default EMBEDDING_PROVIDER); voyage "
        "needs the provider's key, local needs no key",
    )
    parser.add_argument(
        "--kb-cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="vector cache, shared with `make eval-kb` (reruns embed nothing)",
    )
    parser.add_argument("--no-kb-cache", action="store_true", help="do not use the vector cache")
    return parser.parse_args(argv)


def select_scenarios(spec: str) -> list[str]:
    ids = list(SCENARIOS) if spec == "all" else [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [i for i in ids if i not in SCENARIOS]
    if unknown:
        raise SystemExit(f"unknown scenario(s) {unknown}; known: {', '.join(SCENARIOS)}")
    return ids


def select_langs(spec: str) -> list[str]:
    langs = [x.strip() for x in spec.split(",") if x.strip()]
    bad = [x for x in langs if x not in ("es", "en")]
    if bad or not langs:
        raise SystemExit(f"--langs must be es and/or en, got {spec!r}")
    return langs


def needs_cloudflare(ids: list[str]) -> bool:
    """A selected scenario turns the frustration notes on, which need the Cloudflare keys."""
    return any(SCENARIOS[i].frustration_notes for i in ids)


async def open_kb_hub(base: Settings, ids: list[str], args: argparse.Namespace) -> KbHub | None:
    """Build the real index once, up front, if a selected scenario needs it (a down knowledge
    base needs none), so a missing key stops the run before any money is spent."""
    needs = any((kb := SCENARIOS[i].kb) is not None and kb.mode != "down" for i in ids)
    if not needs:
        return None
    settings = base
    if args.kb_provider:
        settings = base.model_copy(update={"embedding_provider": args.kb_provider})
    hub = KbHub(settings, None if args.no_kb_cache else args.kb_cache_dir)
    try:
        await hub.real()
    except KnowledgeError as exc:
        raise SystemExit(
            f"knowledge base: {exc} (set the embedding provider's API key, "
            "or pass --kb-provider local)"
        ) from exc
    return hub


async def run_all(args: argparse.Namespace) -> Path:
    base = Settings()
    problems = missing_keys(base, text_only=True)
    if not base.anthropic_api_key and "ANTHROPIC_API_KEY" not in problems:
        problems.append("ANTHROPIC_API_KEY")  # the simulated candidate and the judge are Claude
    if problems:
        raise SystemExit(f"missing settings: {', '.join(problems)} (set them in .env)")
    ids = select_scenarios(args.scenarios)
    if needs_cloudflare(ids) and not (base.cloudflare_account_id and base.cloudflare_api_token):
        raise SystemExit(
            "the frustration-note scenarios "
            f"({', '.join(i for i in ids if SCENARIOS[i].frustration_notes)}) need "
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (the monitor that sends the notes); "
            "set them in .env or leave those scenarios out"
        )
    redis_url = os.environ.get("EVAL_REDIS_URL", DEFAULT_REDIS_URL)
    if redis_url == base.redis_url:
        raise SystemExit("EVAL_REDIS_URL must differ from the configured REDIS_URL")

    started = datetime.now()
    results_dir = RESULTS_ROOT / started.strftime("%Y%m%d-%H%M%S")
    results_dir.mkdir(parents=True, exist_ok=True)
    langs = select_langs(args.langs)
    redis: Redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception as exc:
        raise SystemExit(f"cannot reach the eval Redis at {redis_url}: {exc}") from exc
    finally:
        await redis.aclose()
    hub = await open_kb_hub(
        base, ids, args
    )  # after the Redis check: it may embed (remote provider)
    cfg = EvalConfig(
        results_dir=results_dir,
        redis_url=redis_url,
        client=anthropic.AsyncAnthropic(api_key=base.anthropic_api_key),
        summary=not args.no_summary,
        judge=not args.no_judge,
        kb=hub,
    )
    jobs = [
        Conversation(SCENARIOS[sid], lang, run, cfg)  # ty: ignore[invalid-argument-type]
        for sid in ids
        for lang in langs
        for run in range(1, args.runs + 1)
    ]
    sem = asyncio.Semaphore(max(args.concurrency, 1))
    records: list[RunRecord] = []
    lines: list[str] = []

    quota_hit = asyncio.Event()

    async def one(job: Conversation) -> None:
        async with sem:
            if quota_hit.is_set():
                # The provider's quota is spent (free tiers have a daily cap): starting more
                # conversations would only burn requests and come back invalid too.
                print(f"skipped {job.key}: provider quota exhausted earlier", flush=True)
                return
            rec = await job.run()
        if rec.harness_status == "provider_quota":
            quota_hit.set()
        records.append(rec)
        status = "PASS" if rec.passed else ("INVALID" if not rec.valid else "FAIL")
        print(f"[{len(records)}/{len(jobs)}] {job.key}: {status} ({rec.seconds}s)", flush=True)
        lines.append(json.dumps(rec.to_json(), ensure_ascii=False, default=str))

    try:
        await asyncio.gather(*(one(j) for j in jobs))
    finally:
        if hub is not None:
            await hub.close()
    records.sort(key=lambda r: (len(r.scenario), r.scenario, r.language, r.run))
    (results_dir / "runs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = ReportMeta(
        started=started.isoformat(timespec="seconds"),
        args=" ".join(sys.argv[1:]) or "(defaults)",
        models=default_models(base.agent_model, base.effective_summary_model),
        agent_provider=base.llm_provider,
        agent_limits=", ".join(
            f"{name}={value:g}"
            for name, value in (
                ("LLM_MAX_RPM", base.llm_max_rpm),
                ("LLM_MAX_TPM", base.llm_max_tpm),
            )
            if value
        ),
        kb=hub.describe() if hub is not None else "",
    )
    (results_dir / "report.md").write_text(render_report(records, meta), encoding="utf-8")
    return results_dir / "report.md"


def main(argv: list[str] | None = None) -> None:
    args: Any = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    path = asyncio.run(run_all(args))
    print(f"\nreport: {path}")


if __name__ == "__main__":
    main()
