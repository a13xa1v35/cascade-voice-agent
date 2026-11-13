"""Render `report.md` from the run records (pure: records in, markdown out)."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from evals.common.usage import Usage, cost
from evals.e2e.llm import JUDGE_MODEL, RUBRIC_BY_ID, SIMULATOR_MODEL
from evals.e2e.records import COMPONENTS, RunRecord, events_of, search_outcome
from hr_screener.observability.metrics import Stats


@dataclass
class ReportMeta:
    started: str
    args: str
    models: dict[str, str] = field(default_factory=dict)  # component -> model
    agent_provider: str = "anthropic"
    agent_limits: str = ""  # e.g. "LLM_MAX_RPM=12, LLM_MAX_TPM=200000"; empty = no client limit
    kb: str = ""  # one line about the knowledge index (provider, model, embedding work)


def arm(run: RunRecord) -> str:
    """The column label: the call language."""
    return run.language


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _sorted_scenarios(runs: Sequence[RunRecord]) -> list[str]:
    return sorted({r.scenario for r in runs}, key=lambda s: (len(s), s))


def pass_rate_section(runs: Sequence[RunRecord]) -> str:
    arms = sorted({arm(r) for r in runs})
    rows = []
    for sc in _sorted_scenarios(runs):
        row: list[object] = [sc]
        for a in arms:
            group = [r for r in runs if r.scenario == sc and arm(r) == a]
            valid = [r for r in group if r.valid]
            cell = f"{sum(r.passed for r in valid)}/{len(valid)}" if group else "-"
            if len(valid) < len(group):
                cell += f" (+{len(group) - len(valid)} invalid)"
            row.append(cell)
        rows.append(row)
    total: list[object] = ["**all**"]
    for a in arms:
        valid = [r for r in runs if arm(r) == a and r.valid]
        total.append(f"{sum(r.passed for r in valid)}/{len(valid)}")
    rows.append(total)
    return (
        "## Pass rate (hard checks)\n\n"
        "Passed / valid runs. A run passes when every hard check passes. Invalid runs "
        "(harness could not create the situation) are listed below and are not counted.\n\n"
        + _table(["scenario", *arms], rows)
    )


def failures_section(runs: Sequence[RunRecord]) -> str:
    lines = ["## Failing checks\n"]
    found = False
    for r in runs:
        if not r.valid:
            continue
        for c in r.checks:
            if not c.passed:
                found = True
                lines.append(f"- **{r.scenario}** / {arm(r)} / run {r.run}: `{c.name}`: {c.detail}")
    if not found:
        lines.append("None.")
    return "\n".join(lines)


def invalid_section(runs: Sequence[RunRecord]) -> str:
    bad = [r for r in runs if not r.valid]
    lines = ["## Invalid runs (harness)\n"]
    if not bad:
        lines.append("None.")
    lines.extend(
        f"- **{r.scenario}** / {arm(r)} / run {r.run}: `{r.harness_status}`: {r.harness_detail}"
        for r in bad
    )
    return "\n".join(lines)


def llm_errors_section(runs: Sequence[RunRecord]) -> str:
    """How reliable Sofia's LLM provider was: every failed request, however the call went on.
    Recovered errors do not fail a run, so this is the only place a flaky provider shows."""
    lines = ["## Sofia LLM errors\n"]
    seen = [(r, c) for r in runs for c in r.calls if c.llm_errors]
    errors = sum(len(c.llm_errors) for _, c in seen)
    recovered = sum(c.llm_errors_recovered for _, c in seen)
    silent = sum(c.unresponsive for _, c in seen)
    gave_up = sum(c.end_reason == "llm_error" for _, c in seen)
    lines.append(
        "Requests of Sofia's LLM that failed (timeout, connection, 5xx, rate limit), counted "
        "over all runs including invalid ones. *Recovered*: the app asked again and the "
        "conversation went on. *Silent*: no reply within the timeout (check `responsive` "
        "fails). *Given up*: two failures in a row, Sofia apologized and ended the call (check "
        "`responsive` fails).\n"
    )
    lines.append(
        _table(
            ["calls with errors", "errors", "recovered by a retry", "silent calls", "given up"],
            [[len(seen), errors, recovered, silent, gave_up]],
        )
    )
    if seen:
        lines.append("\nPer run:\n")
        for r in runs:
            calls = [c for c in r.calls if c.llm_errors]
            if not calls:
                continue
            n = sum(len(c.llm_errors) for c in calls)
            rec = sum(c.llm_errors_recovered for c in calls)
            first = calls[0].llm_errors[0][:100]
            lines.append(
                f"- **{r.scenario}** / {arm(r)} / run {r.run}: {n} error(s), {rec} recovered "
                f"(first: {first!r})"
            )
    return "\n".join(lines)


def drift_section(runs: Sequence[RunRecord]) -> str:
    rows = []
    for sc in _sorted_scenarios(runs):
        for a in sorted({arm(r) for r in runs if r.scenario == sc}):
            turns = [
                d
                for r in runs
                if r.scenario == sc and arm(r) == a
                for c in r.calls
                for d in c.drift
            ]
            if not turns:
                continue
            drifted = [d for d in turns if d.drifted]
            unknown = sum(d.lang == "unknown" for d in turns)
            rows.append([sc, a, len(turns), len(drifted), unknown])
    body = _table(["scenario", "language", "Sofia turns", "drifted", "too short to tell"], rows)
    return (
        "## Language drift (stopword heuristic)\n\n"
        "Per-turn detections are in `runs.jsonl` (`calls[].drift`). 'Too short to tell' turns "
        "(names, dates, 'Vale.') are never counted as drift.\n\n" + body
    )


def judge_section(runs: Sequence[RunRecord]) -> str:
    head = (
        "## LLM judge (UNVALIDATED, reporting only)\n\n"
        "These verdicts come from an LLM judge that has not been checked against hand labels. "
        "They do not affect pass/fail. 'flagged' = the answer that signals a problem.\n"
    )
    judged = [r for r in runs if r.judge]
    errors = [r for r in runs if r.judge_error]
    if not judged and not errors:
        return head + "\nNo judge verdicts (judge off or no valid runs)."
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    flagged_rows: list[str] = []
    for r in judged:
        for v in r.judge:
            counts[v.id][v.answer] += 1
            bad = RUBRIC_BY_ID.get(v.id, ("", "", None))[2]
            if bad is not None and v.answer == bad:
                where = f"{r.scenario}/{arm(r)}/run {r.run}" + (f"/call {v.call}" if v.call else "")
                quote = repr(v.evidence) if not v.evidence_dropped else "(quote not found)"
                flagged_rows.append(f"- `{v.id}` {where}: {quote}")
    rows = []
    for qid in RUBRIC_BY_ID:
        if qid not in counts:
            continue
        c = counts[qid]
        bad = RUBRIC_BY_ID[qid][2]
        rows.append([qid, c["yes"], c["no"], c["n/a"], c[bad] if bad else "-"])
    out = [head, _table(["question", "yes", "no", "n/a", "flagged"], rows)]
    dropped = sum(v.evidence_dropped for r in judged for v in r.judge)
    total = sum(1 for r in judged for v in r.judge if v.evidence or v.evidence_dropped)
    if dropped:
        out.append(
            f"\nEvidence dropped: {dropped} of {total} quotes were not found in the transcript "
            "of the call they name, so those verdicts are shown without evidence."
        )
    if flagged_rows:
        out += ["\nFlagged evidence:\n", *flagged_rows[:40]]
    if errors:
        out += [
            "\nJudge errors:\n",
            *[f"- {r.scenario}/{arm(r)}/run {r.run}: {r.judge_error}" for r in errors],
        ]
    return "\n".join(out)


def kb_section(runs: Sequence[RunRecord], meta: ReportMeta) -> str:
    """Per knowledge scenario: how the searches ended, how results were delivered and how
    many questions were referred (from the recorded events), summed over its runs."""
    kb_runs = [r for r in runs if r.kb_mode and r.valid]
    if not kb_runs:
        return ""
    rows = []
    for sc in _sorted_scenarios(kb_runs):
        for a in sorted({arm(r) for r in kb_runs if r.scenario == sc}):
            group = [r for r in kb_runs if r.scenario == sc and arm(r) == a]
            calls = [c for r in group for c in r.calls]
            outcomes = [search_outcome(e["data"]) for c in calls for e in events_of(c, "kb_search")]
            delivered = [
                e["data"].get("mode") for c in calls for e in events_of(c, "kb_result_delivered")
            ]
            holding = sum(len(events_of(c, "kb_holding_line")) for c in calls)
            rows.append(
                [
                    sc,
                    a,
                    group[0].kb_mode,
                    len(group),
                    f"{outcomes.count('found')}/{outcomes.count('no_match')}/"
                    f"{outcomes.count('unavailable')}",
                    f"{delivered.count('inline')}/{delivered.count('deferred')}",
                    holding,
                    sum(len(c.referred_questions) for c in calls),
                ]
            )
    table = _table(
        [
            "scenario",
            "language",
            "kb",
            "runs",
            "searches found/no_match/unavailable",
            "delivered inline/deferred",
            "holding lines",
            "questions referred",
        ],
        rows,
    )
    head = "## Knowledge base\n\n" + (meta.kb + "\n\n" if meta.kb else "")
    return head + table


def usage_section(runs: Sequence[RunRecord], models: dict[str, str]) -> str:
    total = {c: Usage() for c in COMPONENTS}
    for r in runs:
        for c in COMPONENTS:
            total[c].add(r.usage[c])
    n = max(len(runs), 1)
    rows = []
    grand = 0.0
    for c in COMPONENTS:
        u, model = total[c], models.get(c)
        usd = cost(u, model)
        grand += usd or 0.0
        rows.append(
            [
                c,
                model or "-",
                u.calls,
                u.input_tokens,
                u.output_tokens,
                u.cache_read_tokens,
                u.reasoning_tokens if c == "agent" else "-",
                f"${usd:.4f}" if usd is not None else "unknown model price",
                f"${usd / n:.4f}" if usd is not None else "-",
            ]
        )
    table = _table(
        [
            "component",
            "model",
            "calls",
            "input tok",
            "output tok",
            "cache read tok",
            "of which reasoning",
            "cost",
            "cost / conversation",
        ],
        rows,
    )
    notes = (
        f"{len(runs)} conversations. Total ${grand:.4f} for components with a known price. "
        "'input tok' excludes cache reads, which are priced at the model's cache-read rate "
        "(at the plain input rate where none is known, an upper bound); cache writes are not "
        "priced. Reasoning tokens are already inside 'output tok' (both providers count them "
        "there), so they are shown but never priced twice.\n\n"
        "- **agent**: pipecat usage metrics stored by the app (`call_metrics.prompt_tokens` / "
        "`completion_tokens` / `cache_read_tokens` / `reasoning_tokens`). OpenAI reports the "
        "prompt gross of the cache, so its cache reads are subtracted from 'input tok'; "
        "Anthropic reports it net already. Cache *write* tokens are not exposed.\n"
        "- **simulator**, **judge**: `response.usage` of each call.\n"
        "- **summary**: `response.usage` of the post-call summary, measured by wrapping the "
        "client's `parse` calls (0 with `--no-summary`).\n"
    )
    return "## Token usage and cost\n\n" + table + "\n\n" + notes


def latency_section(runs: Sequence[RunRecord]) -> str:
    """Time to first byte of Sofia's LLM requests, pooled over every request of the run."""
    rows = []
    for a in sorted({arm(r) for r in runs}):
        values = [v for r in runs if arm(r) == a for v in r.llm_ttfb_secs]
        if not values:
            continue
        st = Stats.of(values)
        rows.append([a, st.count, f"{st.p50:.3f}", f"{st.p95:.3f}", f"{st.max:.3f}"])
    body = (
        _table(["language", "requests", "p50 s", "p95 s", "max s"], rows)
        if rows
        else "No time-to-first-byte data."
    )
    return (
        "## Sofia LLM latency (time to first byte)\n\n"
        "Pipecat's TTFB metric for each request Sofia's LLM made, pooled over all valid and "
        "invalid runs. It excludes any wait for the client-side rate limiter "
        "(`LLM_MAX_RPM` / `LLM_MAX_TPM`), which happens before the request starts.\n\n" + body
    )


def render_report(runs: Sequence[RunRecord], meta: ReportMeta) -> str:
    models = "\n".join(f"- {k}: `{v}`" for k, v in meta.models.items())
    limits = meta.agent_limits or "none"
    parts = [
        f"# Eval report {meta.started}\n",
        f"Command: `{meta.args}`\n\nSofia: provider `{meta.agent_provider}`, model "
        f"`{meta.models.get('agent', '-')}` (client-side rate limit: {limits})\n\n{models}\n",
        pass_rate_section(runs),
        failures_section(runs),
        invalid_section(runs),
        llm_errors_section(runs),
        drift_section(runs),
        judge_section(runs),
        kb_section(runs, meta),
        usage_section(runs, meta.models),
        latency_section(runs),
    ]
    return "\n\n".join(p for p in parts if p) + "\n"


def default_models(agent: str, summary: str) -> dict[str, str]:
    return {"agent": agent, "simulator": SIMULATOR_MODEL, "judge": JUDGE_MODEL, "summary": summary}
