"""Build an in-memory index and run one query in the three retrieval modes.

Hybrid goes through the app's own `QdrantKnowledgeBase.search` (so the eval measures the code
that serves calls). The package has no dense-only or BM25-only search, so those two query the
same collection through the Qdrant client directly.
"""

from dataclasses import dataclass
from typing import Final

from qdrant_client import AsyncQdrantClient, models

from evals.kb.golden import GoldenItem
from evals.kb.metrics import Outcome, first_hit_rank
from hr_screener.knowledge.chunking import Chunk
from hr_screener.knowledge.embeddings import Embedder, SparseEncoder
from hr_screener.knowledge.store import DENSE, SPARSE, QdrantKnowledgeBase

MODES: Final = ("hybrid", "dense", "bm25")


@dataclass(frozen=True)
class Retrieval:
    ranked: dict[str, list[str]]  # mode -> chunk ids, best first
    dense_scores: dict[str, float]  # chunk id -> dense cosine, for the dense top results
    bm25_scores: dict[str, float]
    best_dense: float | None


async def build_index(
    chunks: list[Chunk], embedder: Embedder, sparse: SparseEncoder
) -> QdrantKnowledgeBase:
    """Always `:memory:`: never the app's QDRANT_PATH, which is locked while the server runs."""
    kb = QdrantKnowledgeBase(AsyncQdrantClient(":memory:"), embedder, sparse, min_score=0.0)
    await kb.sync(chunks)
    return kb


async def _scored(kb: QdrantKnowledgeBase, **query: object) -> list[tuple[str, float]]:
    res = await kb.client.query_points(kb.collection, with_payload=["chunk_id"], **query)  # ty: ignore[invalid-argument-type]
    return [(str((p.payload or {}).get("chunk_id", "")), float(p.score)) for p in res.points]


async def retrieve(kb: QdrantKnowledgeBase, query: str, depth: int) -> Retrieval:
    dense_vec = await kb.embedder.embed_query(query)
    dense = await _scored(kb, query=dense_vec, using=DENSE, limit=depth)
    sp = kb.sparse.embed_query(query)
    bm25 = await _scored(
        kb,
        query=models.SparseVector(indices=sp.indices, values=sp.values),
        using=SPARSE,
        limit=depth,
    )
    hybrid = await kb.search(query, k=depth)
    return Retrieval(
        ranked={
            "hybrid": [h.id for h in hybrid.hits],
            "dense": [cid for cid, _ in dense],
            "bm25": [cid for cid, _ in bm25],
        },
        dense_scores=dict(dense),
        bm25_scores=dict(bm25),
        best_dense=dense[0][1] if dense else None,
    )


SOURCES: Final = ("query_es", "question")


@dataclass(frozen=True)
class QueryRecord:
    """One (query source, mode, golden item) result: what runs.jsonl stores."""

    source: str
    mode: str
    query: str
    outcome: Outcome
    scores: dict[str, float]  # score of each retrieved id in this mode (dense cosine for hybrid)

    def to_json(self) -> dict[str, object]:
        o = self.outcome
        return {
            "source": self.source,
            "mode": self.mode,
            "id": o.item_id,
            "lang": o.lang,
            "tags": list(o.tags),
            "out_of_scope": o.out_of_scope,
            "query": self.query,
            "expected": list(o.expected),
            "ranked": list(o.ranked),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "best_dense": None if o.best_dense is None else round(o.best_dense, 4),
            "hit_rank": first_hit_rank(o.expected, o.ranked),
            "error": o.error,
        }


async def run_queries(
    kb: QdrantKnowledgeBase,
    items: list[GoldenItem],
    depth: int,
    sources: tuple[str, ...] = SOURCES,
) -> list[QueryRecord]:
    """Every item x source x mode. A query that raises is recorded as invalid, not as a miss."""
    records: list[QueryRecord] = []
    for source in sources:
        for item in items:
            query = getattr(item, source)
            try:
                result = await retrieve(kb, query, depth)
            except Exception as exc:  # embedding / store failure: report as invalid
                err = f"{type(exc).__name__}: {exc}"
                records.extend(
                    QueryRecord(source, mode, query, _outcome(item, (), None, err), {})
                    for mode in MODES
                )
                continue
            for mode in MODES:
                scores = result.bm25_scores if mode == "bm25" else result.dense_scores
                ranked = result.ranked[mode]
                records.append(
                    QueryRecord(
                        source,
                        mode,
                        query,
                        _outcome(item, tuple(ranked), result.best_dense, None),
                        {c: scores[c] for c in ranked if c in scores},
                    )
                )
    return records


def _outcome(
    item: GoldenItem, ranked: tuple[str, ...], best: float | None, error: str | None
) -> Outcome:
    return Outcome(
        item_id=item.id,
        lang=item.lang,
        tags=item.tags,
        expected=item.expected,
        out_of_scope=item.out_of_scope,
        ranked=ranked,
        best_dense=best,
        error=error,
    )
