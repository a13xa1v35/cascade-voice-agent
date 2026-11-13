# ruff: noqa: E501  (report text)
"""Offline replay: re-ask the system-one model (question set v2) about the states logged in a
finished run, and show what the v2 policy would have done with them.

    uv run python -m evals.turn_taking.replay_system_one [--run evals/results/turn_taking/system-one-telephony]
        [--config evals/turn_taking/configs/system_one_v2.yaml] [--dry-run]

Limits (also printed in the report header): every state is judged IN ISOLATION. The replay cannot
simulate the timing dynamics (debounce, consecutive-judgment confirmations, silence re-asks,
what the agent would have been saying). `has_final` is approximated from the run's `stt.final`
events, `turn_open` as "agent idle", and consecutive confirmations are assumed satisfied.
Only the system-one model (Cloudflare Workers AI) is called; no STT/TTS/LLM.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from evals.turn_taking.config import load_config, resolve_settings
from evals.turn_taking.designs import DESIGNS
from evals.turn_taking.variants import VARIANTS
from hr_screener.turn_taking.design import make_system_one_classifier
from hr_screener.turn_taking.policy import (
    SYSTEM_ONE_QUESTIONS,
    Action,
    Inputs,
    Knobs,
    Scores,
    TurnPolicy,
    normalize_words,
)

CANDOR = {"candor_turn_taking", "candor_pause_handling"}
MAX_CALLS = 300
SPACING_SECS = 0.3


@dataclass
class Case:
    category: str  # cold_start | statement | interruption | backchannel | side_talk
    task: str
    sample: str
    t: float
    transcript: str
    busy: bool
    silence_secs: float
    vad_speaking: bool
    has_final: bool
    state: dict[str, Any]
    v1_scores: dict[str, float]
    v1_action: str
    v2_scores: dict[str, float] = field(default_factory=dict)
    v2_action: str = ""
    error: str = ""


def _events(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else []


def _vad_speaking_at(events: list[dict], t: float) -> bool:
    speaking = False
    for e in events:
        if e["t"] > t:
            break
        if e["type"] == "vad.user_started":
            speaking = True
        elif e["type"] == "vad.user_stopped":
            speaking = False
    return speaking


def _has_final(events: list[dict], t: float, transcript: str) -> bool:
    finals = " ".join(e["text"] for e in events if e["type"] == "stt.final" and e["t"] <= t)
    fw, tw = normalize_words(finals), normalize_words(transcript)
    if not tw:
        return False
    return any(fw[i : i + len(tw)] == tw for i in range(len(fw) - len(tw) + 1))


def _make_case(
    category: str, j: dict, *, version: str, task: str, sid: str, events: list[dict]
) -> Case:
    return Case(
        category=category,
        task=f"{version}/{task}",
        sample=sid,
        t=j["t"],
        transcript=j["transcript"],
        busy=bool(j["bot_speaking"]),
        silence_secs=float(j["silence_secs"]),
        vad_speaking=_vad_speaking_at(events, j["t"]),
        has_final=_has_final(events, j["t"], j["transcript"]),
        state=j["state"],
        v1_scores=j["scores"],
        v1_action=j["action"],
    )


def collect(run_dir: Path) -> list[Case]:
    cases: list[Case] = []
    for sample_dir in sorted(run_dir.glob("v*/*/*")):
        if not (sample_dir / "events.json").exists():
            continue
        version, task, sid = sample_dir.parts[-3:]
        events = _events(sample_dir / "events.json")
        judgments = [e for e in events if e["type"] == "system1.judgment" and e.get("scores")]

        mk = partial(_make_case, version=version, task=task, sid=sid, events=events)

        if task in CANDOR:
            fallback_ts = [
                e["t"]
                for e in events
                if e["type"] == "system1.action" and e.get("action") == "fallback"
            ]
            cases += [mk("cold_start", j) for j in judgments if j["action"] == "drop_side_talk"]
            for ft in fallback_ts:
                prior = [j for j in judgments if j["t"] <= ft]
                if prior:
                    cases.append(mk("statement", prior[-1]))
        elif task == "user_interruption":
            meta = json.loads((sample_dir / "metadata.json").read_text())
            lo, hi = meta["timestamps"]
            cases += [mk("interruption", j) for j in judgments if lo <= j["t"] <= hi]
        elif task == "user_backchannel":
            cases += [mk("backchannel", j) for j in judgments if j["bot_speaking"]]
        elif task in ("talking_to_other", "background_speech"):
            cases += [mk("side_talk", j) for j in judgments if j["bot_speaking"]]
    return _dedupe_and_cap(cases)


def _dedupe_and_cap(cases: list[Case]) -> list[Case]:
    seen: set[tuple] = set()
    out: list[Case] = []
    for c in cases:
        key = (c.category, c.task, c.sample, c.transcript, c.busy)
        if c.category in ("cold_start", "statement"):
            key = (c.category, c.transcript)  # identical transcripts across samples
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    # candor categories: about 40 in total, drops first, then fallback statements
    candor = [c for c in out if c.category in ("cold_start", "statement")]
    rest = [c for c in out if c.category not in ("cold_start", "statement")]
    drops = [c for c in candor if c.category == "cold_start"]
    statements = [c for c in candor if c.category == "statement"]
    return drops[:30] + statements[:10] + rest


def v2_decision(c: Case, scores: Scores, policy: TurnPolicy) -> Action:
    inputs = Inputs(
        scores=scores,
        classifier_failed=False,
        transcript=c.transcript,
        has_final=c.has_final,
        vad_speaking=c.vad_speaking,
        silence_secs=c.silence_secs,
        agent_busy=c.busy,
        turn_open=not c.busy,
        low_addressed_count=policy.k.side_talk_confirmations,  # confirmations assumed satisfied
    )
    return policy.decide(inputs).action


async def replay(cases: list[Case], classifier: Any, policy: TurnPolicy) -> None:
    for n, c in enumerate(cases, 1):
        try:
            res = await classifier.yes_no(c.state, SYSTEM_ONE_QUESTIONS)
            c.v2_scores = {k: round(r.probability, 3) for k, r in res.items()}
            c.v2_action = v2_decision(c, Scores(**c.v2_scores), policy).value
        except Exception as e:
            c.error = repr(e)
        if n % 20 == 0:
            print(f"  {n}/{len(cases)}", flush=True)
        await asyncio.sleep(SPACING_SECS)


# --- report -------------------------------------------------------------------------------


def _s(scores: dict[str, float], key: str) -> str:
    return f"{scores[key]:.2f}" if key in scores else "-"


def summarize(cases: list[Case], knobs: Knobs) -> tuple[list[str], list[str]]:
    ok = [c for c in cases if not c.error]
    lines: list[str] = []
    flags: list[str] = []

    cold = [c for c in ok if c.category == "cold_start"]
    no_drop = [c for c in cold if c.v2_scores["addressed_to_agent"] >= knobs.addressed_threshold]
    still = [c for c in cold if c.v2_action == Action.DROP_SIDE_TALK]
    lines.append(
        f"- **Cold-start drops (candor, v1 `drop_side_talk`)**: {len(cold)} cases; "
        f"v2 `addressed` >= {knobs.addressed_threshold}: **{len(no_drop)}** no longer dropped; the v2 policy still "
        f"drops {len(still)} (with confirmations satisfied)."
    )

    stm = [c for c in ok if c.category == "statement"]
    n = len(stm)

    def count(key: str, thr: float, which: str = "v2") -> int:
        return sum(1 for c in stm if (c.v2_scores if which == "v2" else c.v1_scores)[key] >= thr)

    lines.append(
        f"- **Statements (last judgment before a 5 s fallback)**: {n} cases; "
        f"`turn_complete` >= 0.55: v1 {count('turn_complete', 0.55, 'v1')} -> v2 **{count('turn_complete', 0.55)}**; "
        f">= 0.72: v1 {count('turn_complete', 0.72, 'v1')} -> v2 **{count('turn_complete', 0.72)}**; "
        f">= v2 floor {knobs.complete_floor}: **{count('turn_complete', knobs.complete_floor)}**."
    )

    intr = [c for c in ok if c.category == "interruption"]
    by_sample: dict[str, list[Case]] = {}
    for c in intr:
        by_sample.setdefault(c.sample, []).append(c)
    rows = []
    v1_cross = v2_cross = 0
    for sid, cs in sorted(by_sample.items()):
        cs.sort(key=lambda c: c.t)
        f1 = next((c for c in cs if c.v1_action == Action.INTERRUPT), None)
        f2 = next((c for c in cs if c.v2_action == Action.INTERRUPT), None)
        v1_cross += f1 is not None
        v2_cross += f2 is not None
        w = lambda c: f"{len(c.transcript.split())} words @ {c.t:.1f}s" if c else "never"  # noqa: E731
        rows.append(f"    - sample {sid}: v1 {w(f1)}; v2 {w(f2)}")
    lines.append(
        f"- **Interruptions (overlap window)**: {len(by_sample)} samples; first interrupt decision "
        f"in the window: v1 **{v1_cross}**, v2 **{v2_cross}**. Words in / time of crossing:"
    )
    lines += rows

    bc = [c for c in ok if c.category == "backchannel"]
    max_tk = max((c.v2_scores["taking_floor"] for c in bc), default=0.0)
    max_nr = max((c.v2_scores.get("new_request", 0.0) for c in bc), default=0.0)
    bad_bc = [c for c in bc if c.v2_action == Action.INTERRUPT]
    lines.append(
        f"- **Backchannels (busy agent)**: {len(bc)} cases; max v2 `taking_floor` **{max_tk:.2f}**, "
        f"max `new_request` **{max_nr:.2f}** (taking threshold {knobs.taking_threshold}, "
        f"new_request threshold {knobs.new_request_threshold})."
    )
    if bad_bc:
        flags.append(
            f"REGRESSION: {len(bad_bc)} backchannel judgment(s) would now INTERRUPT: "
            + "; ".join(f"{c.sample}@{c.t:.1f}s {c.transcript!r}" for c in bad_bc)
        )

    side = [c for c in ok if c.category == "side_talk"]
    v1_drop = [c for c in side if c.v1_action == Action.DROP_SIDE_TALK]
    v2_drop = [c for c in side if c.v2_action == Action.DROP_SIDE_TALK]
    lost = [c for c in v1_drop if c.v2_action != Action.DROP_SIDE_TALK]
    bad_side = [c for c in side if c.v2_action == Action.INTERRUPT]
    lines.append(
        f"- **Side talk (talking_to_other / background_speech, busy agent)**: {len(side)} cases; "
        f"v1 dropped {len(v1_drop)}, v2 still drops **{len(v2_drop)}**; "
        f"v1-dropped but not v2: **{len(lost)}**; v2 would interrupt: **{len(bad_side)}**."
    )
    if lost:
        flags.append(
            f"REGRESSION: {len(lost)} side-talk judgment(s) v1 dropped are no longer dropped by v2 "
            "(could leak to the LLM if sustained): "
            + "; ".join(
                f"{c.task.split('/')[-1]} {c.sample}@{c.t:.1f}s {c.transcript[:40]!r}"
                for c in lost[:12]
            )
        )
    if bad_side:
        flags.append(
            f"REGRESSION: {len(bad_side)} side-talk judgment(s) would now INTERRUPT: "
            + "; ".join(f"{c.sample}@{c.t:.1f}s {c.transcript[:40]!r}" for c in bad_side[:12])
        )
    errs = [c for c in cases if c.error]
    if errs:
        lines.append(f"- **Errors**: {len(errs)} case(s) failed to judge (excluded above).")
    return lines, flags


def render(cases: list[Case], run: Path, params: dict[str, Any], knobs: Knobs) -> str:
    lines, flags = summarize(cases, knobs)
    out = [
        "# system_one v2 replay (offline, for review)",
        "",
        f"Source run: `{run}`. Judged {len(cases)} logged states with question set `"
        f"{params['question_set']}` (sha `{params['question_set_sha']}`), through the hedged "
        "system-one classifier, sequentially.",
        "",
        "> **Limits.** Each state is judged in isolation. The replay cannot simulate timing dynamics: "
        "debounce, consecutive-judgment confirmations (assumed satisfied), silence re-asks, or what "
        "the agent would have been saying. `has_final` is approximated from the run's `stt.final` "
        'events, `turn_open` as "agent idle". The v2 action is the pure `TurnPolicy` on the logged '
        "`silence_secs` / `bot_speaking`, with these knobs: "
        + ", ".join(
            f"`{k}={params[k]}`"
            for k in sorted(Knobs().as_params())
            if params[k] != DESIGNS["v1"][k]  # listed against the design that produced the run
        )
        + ".",
        "",
        "## Summary",
        "",
        *lines,
    ]
    if flags:
        out += ["", "## REGRESSIONS", "", *[f"- **{f}**" for f in flags]]
    out += [
        "",
        "## Cases",
        "",
        "Scores are `turn_complete / addressed / taking` (v1) and `... / new_request` (v2).",
        "",
        "| category | task | id | t | busy | transcript | v1 scores | v2 scores | v1 action | v2 action |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in cases:
        v1 = "/".join(
            _s(c.v1_scores, k) for k in ("turn_complete", "addressed_to_agent", "taking_floor")
        )
        v2 = (
            "/".join(
                _s(c.v2_scores, k)
                for k in ("turn_complete", "addressed_to_agent", "taking_floor", "new_request")
            )
            if c.v2_scores
            else f"ERROR {c.error[:30]}"
        )
        text = c.transcript.replace("|", "/")[:70]
        out.append(
            f"| {c.category} | {c.task.split('/')[-1]} | {c.sample} | {c.t:.1f} "
            f"| {'Y' if c.busy else ''} | {text} | {v1} | {v2} | {c.v1_action} | {c.v2_action} |"
        )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default="evals/results/turn_taking/system-one-telephony")
    ap.add_argument("--config", default="evals/turn_taking/configs/system_one_v2.yaml")
    ap.add_argument("--out", default="evals/turn_taking/reports/system-one-v2-replay.md")
    ap.add_argument("--dry-run", action="store_true", help="count the cases, make no calls")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    variant = VARIANTS[cfg.agent.variant]
    params = variant.resolve_params(cfg.agent.variant_params, design=cfg.agent.design)
    knobs = Knobs(**{k: params[k] for k in Knobs().as_params()})
    cases = collect(Path(args.run))
    by_cat: dict[str, int] = {}
    for c in cases:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
    print(f"{len(cases)} cases to judge: {by_cat}")
    if len(cases) > MAX_CALLS:
        sys.exit(f"{len(cases)} calls > {MAX_CALLS}; tighten the case selection")
    if args.dry_run:
        return 0
    settings = resolve_settings(cfg)
    if missing := [k for k in variant.required_keys if not getattr(settings, k)]:
        sys.exit(f"missing {missing} in the env_file")
    classifier = make_system_one_classifier(settings, params)

    async def go() -> None:
        try:  # clients connect lazily on the first question
            await replay(cases, classifier, TurnPolicy(knobs))
        finally:
            await classifier.cleanup()

    t = time.monotonic()
    asyncio.run(go())
    report = render(cases, Path(args.run), params, knobs)
    Path(args.out).write_text(report)
    print(f"wrote {args.out} ({len(cases)} calls, {time.monotonic() - t:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
