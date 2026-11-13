"""Render `report.md` from the query records (pure: records in, markdown out)."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from evals.kb.embed_cache import EmbedStats
from evals.kb.metrics import (
    DEFAULT_THRESHOLDS,
    RECALL_TOLERANCE,
    Outcome,
    SweepRow,
    first_hit_rank,
    group_by,
    mrr,
    no_match_stats,
    recall_at_k,
    recommend_threshold,
    sweep,
)
from evals.kb.retrieval import MODES, SOURCES, QueryRecord

SOURCE_LABEL = {
    "query_es": "`query_es` (Spanish query, normal path)",
    "question": "`question` (raw words, model forgot to translate)",
}
FAILURES_PER_RUN = 25


@dataclass
class ReportMeta:
    started: str
    args: str
    provider: str  # openai | voyage | local
    model: str
    dim: int
    kb_dir: str
    n_chunks: int
    min_score: float  # configured KB_MIN_SCORE
    k: int  # production KB_TOP_K
    stats: EmbedStats
    cache: str  # cache file description or "off"


def _f(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def ks_for(k: int) -> list[int]:
    return sorted({1, 4, 8, k})


def index_runs(records: Sequence[QueryRecord]) -> dict[tuple[str, str], list[QueryRecord]]:
    runs: dict[tuple[str, str], list[QueryRecord]] = defaultdict(list)
    for r in records:
        runs[(r.source, r.mode)].append(r)
    return runs


def outcomes_of(records: Sequence[QueryRecord]) -> list[Outcome]:
    return [r.outcome for r in records]


def sweep_for_source(
    runs: dict[tuple[str, str], list[QueryRecord]], source: str, k: int
) -> tuple[list[SweepRow], SweepRow | None]:
    """Sweep over the hybrid outcomes (what the app serves); the best dense score does not
    depend on the mode, only the recall half of the rule does."""
    outcomes = outcomes_of(runs.get((source, "hybrid"), []))
    rows = sweep(outcomes, k, DEFAULT_THRESHOLDS)
    return rows, recommend_threshold(rows, recall_at_k(outcomes, k), RECALL_TOLERANCE)


def retrieval_section(runs: dict[tuple[str, str], list[QueryRecord]], k: int) -> str:
    ks = ks_for(k)
    rows = []
    for source in SOURCES:
        for mode in MODES:
            outs = outcomes_of(runs.get((source, mode), []))
            if not outs:
                continue
            n = len([o for o in outs if o.valid and not o.out_of_scope])
            rows.append(
                [f"`{source}`", mode, n] + [_f(recall_at_k(outs, x)) for x in ks] + [_f(mrr(outs))]
            )
    headers = ["query source", "mode", "in-scope n"] + [f"recall@{x}" for x in ks] + ["MRR"]
    return (
        "## Retrieval (in-scope items)\n\n"
        f"recall@k = share of questions with an expected chunk in the top k; the app returns "
        f"k={k}. MRR = mean 1/rank of the first expected chunk (0 if not in the top "
        f"{max(ks)}).\n\n" + _table(headers, rows)
    )


def no_match_section(
    runs: dict[tuple[str, str], list[QueryRecord]], k: int, min_score: float
) -> tuple[str, dict[str, float]]:
    """The text, and the recommended threshold per query source."""
    parts = [
        "## No-match threshold\n\n"
        "The app answers `no_match` when the best dense cosine over the collection is below "
        "`KB_MIN_SCORE`. That score does not depend on the retrieval mode, so one sweep per "
        "query source. Positive class = out-of-scope item (should be `no_match`); precision "
        "= flagged items that really are out of scope, recall = out-of-scope items flagged. "
        "`gated recall@k` is in-scope recall@k when an item below the threshold counts as a "
        "miss.\n\n"
        f"**Rule:** recommend the threshold with the highest no-match F1 among those whose "
        f"gated in-scope recall@{k} is within {RECALL_TOLERANCE:.2f} of the ungated recall@{k}; "
        "ties go to higher gated recall, then the lower threshold."
    ]
    chosen: dict[str, float] = {}
    for source in SOURCES:
        if (source, "hybrid") not in runs:
            continue
        rows, rec = sweep_for_source(runs, source, k)
        outs = outcomes_of(runs[(source, "hybrid")])
        base = recall_at_k(outs, k)
        table = _table(
            ["threshold", "precision", "recall", "F1", "TP", "FP", "FN", f"gated recall@{k}", ""],
            [
                [
                    f"{r.stats.threshold:.2f}",
                    _f(r.stats.precision),
                    _f(r.stats.recall),
                    _f(r.stats.f1),
                    r.stats.tp,
                    r.stats.fp,
                    r.stats.fn,
                    _f(r.gated_recall),
                    "**recommended**" if rec is r else "",
                ]
                for r in rows
            ],
        )
        cur = no_match_stats(outs, min_score)
        text = [f"### {SOURCE_LABEL[source]}", f"Ungated recall@{k}: {_f(base)}.", table]
        if rec is not None:
            chosen[source] = rec.stats.threshold
            text.append(
                f"Recommended `KB_MIN_SCORE` = **{rec.stats.threshold:.2f}** "
                f"(F1 {_f(rec.stats.f1)}, precision {_f(rec.stats.precision)}, "
                f"recall {_f(rec.stats.recall)}, gated recall@{k} {_f(rec.gated_recall)})."
            )
        text.append(
            f"At the configured `KB_MIN_SCORE` = {min_score:.2f}: F1 {_f(cur.f1)}, "
            f"precision {_f(cur.precision)}, recall {_f(cur.recall)}."
        )
        parts.append("\n\n".join(text))
    return "\n\n".join(parts), chosen


def breakdown_section(
    runs: dict[tuple[str, str], list[QueryRecord]], k: int, chosen: dict[str, float]
) -> str:
    combos = [(s, m) for s in SOURCES for m in MODES if (s, m) in runs]
    head = [f"`{s}`/{m}" for s, m in combos]
    any_outs = outcomes_of(runs[combos[0]]) if combos else []

    def labels(o: Outcome) -> list[str]:
        return [f"lang={o.lang}", *[f"tag={t}" for t in o.tags if t != "near"]]

    scoped = {lbl for o in any_outs if not o.out_of_scope for lbl in labels(o)}
    rows = []
    for lbl in sorted(scoped):
        cells: list[object] = []
        n = 0
        for combo in combos:
            outs = group_by(outcomes_of(runs[combo]), labels).get(lbl, [])
            n = len([o for o in outs if o.valid and not o.out_of_scope])
            cells.append(f"{_f(recall_at_k(outs, k))} / {_f(mrr(outs))}")
        rows.append([lbl, n, *cells])
    text = [
        f"## Breakdown\n\nIn-scope items, cells are `recall@{k} / MRR`.\n\n"
        + _table(["group", "n", *head], rows)
    ]

    oos_rows = []
    oos_groups = sorted(
        {lbl for o in any_outs if o.out_of_scope for lbl in ["all", f"lang={o.lang}", *o.tags]}
    )
    for lbl in oos_groups:
        row: list[object] = [lbl]
        for source in SOURCES:
            if (source, "hybrid") not in runs or source not in chosen:
                row.append("-")
                continue
            outs = [o for o in outcomes_of(runs[(source, "hybrid")]) if o.valid and o.out_of_scope]
            sel = [o for o in outs if lbl == "all" or lbl == f"lang={o.lang}" or lbl in o.tags]
            stats = no_match_stats(sel, chosen[source])
            row.append(f"{stats.tp}/{stats.tp + stats.fn}")
        oos_rows.append(row)
    text.append(
        "Out-of-scope items correctly returned as `no_match` at each source's recommended "
        "threshold (`near` = close to topics the knowledge base covers):\n\n"
        + _table(["group", *[f"`{s}`" for s in SOURCES]], oos_rows)
    )
    return "\n\n".join(text)


def cost_section(meta: ReportMeta) -> str:
    s = meta.stats
    lines = [
        "## Embedding cost",
        f"Provider `{meta.provider}`, model `{meta.model}` ({meta.dim} dims). Cache: {meta.cache}.",
        f"- texts embedded this run (cache misses): {s.texts_embedded} ({s.chars} characters)",
        f"- cache hits: {s.cache_hits}",
    ]
    if meta.provider == "local":
        lines.append("- cost: $0 (local ONNX model, no API call)")
    else:
        lines.append(f"- {meta.provider} API calls: {s.api_calls}; tokens billed: {s.tokens}")
        lines.append(
            "- cost: tokens x the current price of this model (not tracked here; "
            "Anthropic prices in `evals/common/usage.py` do not apply). A fully cached rerun "
            "shows 0 tokens."
        )
    return "\n".join(lines)


def failures_section(runs: dict[tuple[str, str], list[QueryRecord]], k: int, shown: int) -> str:
    parts = [
        f"## Failures\n\nIn-scope items with no expected chunk in the top {k}. Each retrieved id "
        "shows its score in that mode (hybrid shows the dense cosine, since RRF scores are "
        "rank-based; `-` = outside the dense top results)."
    ]
    for source in SOURCES:
        for mode in MODES:
            recs = [
                r
                for r in runs.get((source, mode), [])
                if r.outcome.valid
                and not r.outcome.out_of_scope
                and not (
                    (rank := first_hit_rank(r.outcome.expected, r.outcome.ranked)) and rank <= k
                )
            ]
            if (source, mode) not in runs:
                continue
            lines = [f"### `{source}` / {mode}: {len(recs)} failure(s)"]
            for r in recs[:shown]:
                o = r.outcome
                got = ", ".join(
                    f"{cid} ({_f(r.scores[cid]) if cid in r.scores else '-'})"
                    for cid in o.ranked[:k]
                )
                rank = first_hit_rank(o.expected, o.ranked)
                lines.append(
                    f'- **{o.item_id}** [{o.lang}] "{r.query}"\n'
                    f"  - expected: {', '.join(o.expected)}"
                    f" (found at rank {rank if rank else f'>{len(o.ranked)}'})\n"
                    f"  - got top-{k}: {got or '(nothing)'}"
                )
            if len(recs) > shown:
                lines.append(f"- ... {len(recs) - shown} more in runs.jsonl")
            parts.append("\n".join(lines))
    return "\n\n".join(parts)


def threshold_failures_section(
    runs: dict[tuple[str, str], list[QueryRecord]], chosen: dict[str, float]
) -> str:
    parts = ["## No-match errors at the recommended threshold"]
    for source, t in chosen.items():
        recs = runs.get((source, "hybrid"), [])
        wrong = [
            r
            for r in recs
            if r.outcome.valid
            and (r.outcome.best_dense is None or r.outcome.best_dense < t) != r.outcome.out_of_scope
        ]
        lines = [f"### `{source}` at {t:.2f}: {len(wrong)} error(s)"]
        for r in wrong:
            o = r.outcome
            kind = (
                "answered although out of scope" if o.out_of_scope else "rejected although in scope"
            )
            lines.append(
                f"- **{o.item_id}** [{o.lang}] {kind}: best dense {_f(o.best_dense)}, "
                f'top hit {o.ranked[0] if o.ranked else "-"}; "{r.query}"'
            )
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def invalid_section(records: Sequence[QueryRecord]) -> str:
    bad = [r for r in records if not r.outcome.valid]
    if not bad:
        return "## Invalid runs\n\nNone: every query completed."
    lines = ["## Invalid runs", "Queries that raised; excluded from every metric above."]
    seen: set[tuple[str, str]] = set()
    for r in bad:
        key = (r.source, r.outcome.item_id)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- `{r.source}` {r.outcome.item_id}: {r.outcome.error}")
    return "\n".join(lines)


def render_report(
    records: Sequence[QueryRecord], meta: ReportMeta, *, failures_shown: int = FAILURES_PER_RUN
) -> str:
    runs = index_runs(records)
    head = [
        "# Knowledge-base retrieval eval",
        f"- started: {meta.started}\n- args: `{meta.args}`\n- knowledge: `{meta.kb_dir}`, "
        f"{meta.n_chunks} chunks; golden items: "
        f"{len({r.outcome.item_id for r in records})}",
    ]
    if meta.provider == "local":
        head.append(
            f"> **These numbers are for the local fallback model (`{meta.model}`), "
            "not a hosted one.** "
            "They are a lower bound and are not comparable with an `openai` or `voyage` run; the "
            "recommended threshold in particular does not transfer between models."
        )
    nm_text, chosen = no_match_section(runs, meta.k, meta.min_score)
    sections = [
        "\n\n".join(head),
        retrieval_section(runs, meta.k),
        nm_text,
        breakdown_section(runs, meta.k, chosen),
        cost_section(meta),
        invalid_section(records),
        threshold_failures_section(runs, chosen),
        failures_section(runs, meta.k, failures_shown),
    ]
    return "\n\n".join(sections) + "\n"
