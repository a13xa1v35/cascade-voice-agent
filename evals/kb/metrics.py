"""Retrieval metrics: pure functions over per-query outcomes (no Qdrant, no embeddings)."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

DEFAULT_THRESHOLDS: tuple[float, ...] = tuple(round(0.20 + 0.05 * i, 2) for i in range(13))
# Recommended threshold may lose at most this much in-scope recall@K versus no threshold.
RECALL_TOLERANCE = 0.05


@dataclass(frozen=True)
class Outcome:
    """One query's result in one retrieval mode."""

    item_id: str
    lang: str
    tags: tuple[str, ...]
    expected: tuple[str, ...]
    out_of_scope: bool
    ranked: tuple[str, ...]  # retrieved chunk ids, best first
    best_dense: float | None  # best dense cosine over the whole collection
    error: str | None = None  # query failed: the run is invalid, excluded from metrics

    @property
    def valid(self) -> bool:
        return self.error is None


def first_hit_rank(expected: Iterable[str], ranked: Sequence[str]) -> int | None:
    """1-based rank of the first expected id in `ranked`, None when absent."""
    wanted = set(expected)
    for rank, cid in enumerate(ranked, 1):
        if cid in wanted:
            return rank
    return None


def in_scope(outcomes: Iterable[Outcome]) -> list[Outcome]:
    return [o for o in outcomes if o.valid and not o.out_of_scope]


def recall_at_k(outcomes: Iterable[Outcome], k: int) -> float | None:
    """Share of in-scope queries with an expected chunk in the top k (None: no queries)."""
    pool = in_scope(outcomes)
    if not pool:
        return None
    return sum((r := first_hit_rank(o.expected, o.ranked)) is not None and r <= k for o in pool) / (
        len(pool)
    )


def mrr(outcomes: Iterable[Outcome]) -> float | None:
    """Mean reciprocal rank of the first expected chunk (0 when it is not retrieved)."""
    pool = in_scope(outcomes)
    if not pool:
        return None
    return sum(1 / r if (r := first_hit_rank(o.expected, o.ranked)) else 0.0 for o in pool) / len(
        pool
    )


def predicts_no_match(o: Outcome, threshold: float) -> bool:
    """Same rule as the app: no_match when the best dense score is below the threshold."""
    return o.best_dense is None or o.best_dense < threshold


@dataclass(frozen=True)
class NoMatchStats:
    """No-match as a detector: positive = out of scope, predicted positive = below threshold."""

    threshold: float
    tp: int  # out of scope, flagged no_match (correct)
    fp: int  # in scope, flagged no_match (the candidate is referred to a recruiter needlessly)
    fn: int  # out of scope, answered anyway (Sofia may answer from an irrelevant chunk)
    tn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def no_match_stats(outcomes: Iterable[Outcome], threshold: float) -> NoMatchStats:
    tp = fp = fn = tn = 0
    for o in outcomes:
        if not o.valid:
            continue
        flagged = predicts_no_match(o, threshold)
        if o.out_of_scope:
            tp, fn = (tp + 1, fn) if flagged else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if flagged else (fp, tn + 1)
    return NoMatchStats(threshold, tp, fp, fn, tn)


def gated_recall_at_k(outcomes: Iterable[Outcome], k: int, threshold: float) -> float | None:
    """In-scope recall@k when a query below the threshold counts as a miss (it returns no_match)."""
    pool = in_scope(outcomes)
    if not pool:
        return None
    hits = 0
    for o in pool:
        rank = first_hit_rank(o.expected, o.ranked)
        hits += rank is not None and rank <= k and not predicts_no_match(o, threshold)
    return hits / len(pool)


@dataclass(frozen=True)
class SweepRow:
    stats: NoMatchStats
    gated_recall: float | None  # in-scope recall@k with the threshold applied


def sweep(
    outcomes: Sequence[Outcome], k: int, thresholds: Sequence[float] = DEFAULT_THRESHOLDS
) -> list[SweepRow]:
    return [
        SweepRow(no_match_stats(outcomes, t), gated_recall_at_k(outcomes, k, t)) for t in thresholds
    ]


def recommend_threshold(
    rows: Sequence[SweepRow], baseline_recall: float | None, tolerance: float = RECALL_TOLERANCE
) -> SweepRow | None:
    """The row that maximises no-match F1 subject to gated recall@k >= baseline - tolerance.

    `baseline_recall` is the in-scope recall@k with no threshold at all. Ties on F1 go to the
    higher gated recall, then to the lower threshold (the safer side for the candidate). When
    no row satisfies the constraint, the row with the best gated recall is returned.
    """
    if not rows:
        return None
    floor = (baseline_recall or 0.0) - tolerance
    ok = [r for r in rows if (r.gated_recall or 0.0) >= floor - 1e-9]
    if not ok:
        return max(rows, key=lambda r: ((r.gated_recall or 0.0), -r.stats.threshold))
    return max(ok, key=lambda r: (r.stats.f1, r.gated_recall or 0.0, -r.stats.threshold))


def group_by(
    outcomes: Iterable[Outcome], key: Callable[[Outcome], Iterable[str]]
) -> dict[str, list[Outcome]]:
    """Group outcomes by one or more labels each (an outcome with two tags lands in both)."""
    groups: dict[str, list[Outcome]] = {}
    for o in outcomes:
        for label in key(o):
            groups.setdefault(label, []).append(o)
    return groups
