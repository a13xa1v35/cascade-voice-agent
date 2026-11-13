"""Qdrant-backed knowledge base: hybrid search over one collection.

One collection (`QDRANT_COLLECTION`) with a named dense vector `dense` (cosine) and a named
sparse vector `bm25` (collection modifier IDF, so Qdrant applies the inverse document
frequency BM25 needs). Point ids are UUIDv5 of the chunk id (Qdrant accepts integers or
UUIDs only), so re-ingesting an edited chunk replaces its point.

Client modes: embedded (`path=QDRANT_PATH`, the default; one process, exclusive folder lock),
a server or Qdrant Cloud (`QDRANT_URL`), or `":memory:"` in tests. All use the same code.

Search = fused hybrid query + a separate dense-only query:

* The fused query runs two prefetches (dense and BM25, 20 candidates each) and merges them
  with reciprocal rank fusion (RRF).
* RRF scores are rank-based and not comparable across queries, and fused results do not
  carry the prefetch scores, so they cannot decide "nothing relevant". A second query,
  dense only with limit 1, returns the best cosine score, and `no_match` is
  `best score < KB_MIN_SCORE`. The two queries run concurrently.

The collection records which embedding model, dimension and sparse encoder built it (the
dimension in the vector config, the rest in the collection metadata). Searching with a
different embedder would compare vectors that cannot be compared, so search refuses with
`IndexMismatch` and says to re-ingest instead of returning nonsense.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from qdrant_client import AsyncQdrantClient, models

from hr_screener.config import Settings
from hr_screener.knowledge.cache import QueryEmbeddingCache
from hr_screener.knowledge.chunking import Chunk, point_id
from hr_screener.knowledge.embeddings import Embedder, SparseEncoder, SparseVector
from hr_screener.knowledge.ingest import sync_chunks
from hr_screener.knowledge.types import (
    Hit,
    IndexMismatch,
    KnowledgeUnavailable,
    SearchResult,
    StoreLocked,
    SyncReport,
)

log = logging.getLogger(__name__)

DENSE = "dense"
SPARSE = "bm25"
PREFETCH_LIMIT = 20


class KnowledgeBase(Protocol):
    """What the rest of the app depends on, so tests and the unavailable stand-in plug in."""

    async def search(self, query: str, k: int) -> SearchResult:
        """Hybrid search; `query` is in KB_LANGUAGE. Raises KnowledgeUnavailable."""
        ...

    async def sync(self, chunks: list[Chunk]) -> SyncReport: ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class StoredPoint:
    """What a sync needs to know about a point already in the collection."""

    chunk_id: str
    content_hash: str
    kb_version: str


def make_client(settings: Settings) -> AsyncQdrantClient:
    """Embedded client on QDRANT_PATH, or a server client when QDRANT_URL is set.

    Raises StoreLocked when the embedded folder is open in another process.
    """
    if settings.qdrant_url:
        return AsyncQdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=30
        )
    path = Path(settings.qdrant_path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        return AsyncQdrantClient(path=str(path))
    except RuntimeError as e:
        if "already accessed by another instance" in str(e):
            raise StoreLocked(
                f"the embedded Qdrant folder {path} is in use by another process (a running "
                "server?). Stop it, or set QDRANT_URL to use a Qdrant server."
            ) from e
        raise


class QdrantKnowledgeBase:
    def __init__(
        self,
        client: AsyncQdrantClient,
        embedder: Embedder,
        sparse: SparseEncoder,
        *,
        collection: str = "knowledge",
        min_score: float = 0.5,
        cache: QueryEmbeddingCache | None = None,
        payload_index: bool = False,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.sparse = sparse
        self.collection = collection
        self.min_score = min_score
        self._cache = cache
        # Embedded and in-memory modes ignore payload indexes (with a warning): server only.
        self._payload_index = payload_index
        self._verified = False
        self._kb_version: str | None = None

    @property
    def fingerprint(self) -> str:
        """Identity of the vectors; part of every chunk's content hash."""
        return f"{self.embedder.model}|{self.embedder.dim}|{self.sparse.name}"

    # --- collection management ---

    def _metadata(self) -> dict[str, Any]:
        return {
            "embedding_model": self.embedder.model,
            "embedding_dim": self.embedder.dim,
            "sparse_encoder": self.sparse.name,
        }

    async def _dense_size(self) -> int | None:
        """Stored dense dimension, None when the collection does not exist."""
        if not await self.client.collection_exists(self.collection):
            return None
        info = await self.client.get_collection(self.collection)
        vectors: Any = info.config.params.vectors
        params = vectors.get(DENSE) if isinstance(vectors, dict) else None
        return int(params.size) if params is not None else -1

    async def _create_collection(self) -> None:
        await self.client.create_collection(
            self.collection,
            vectors_config={
                DENSE: models.VectorParams(size=self.embedder.dim, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
            metadata=self._metadata(),
        )
        if self._payload_index:
            await self.client.create_payload_index(
                self.collection, "kind", models.PayloadSchemaType.KEYWORD
            )

    async def prepare_for_sync(self) -> bool:
        """Create the collection, or recreate it when the dense dimension changed.

        Returns True when it was (re)created. The index is derived data, so replacing it is
        the re-ingest the dimension change calls for.
        """
        size = await self._dense_size()
        recreated = False
        if size is not None and size != self.embedder.dim:
            log.warning(
                "dense dimension changed (%s -> %s): recreating collection %s",
                size,
                self.embedder.dim,
                self.collection,
            )
            await self.client.delete_collection(self.collection)
            size = None
            recreated = True
        if size is None:
            await self._create_collection()
            recreated = True
        self._verified = False
        return recreated

    async def record_model(self) -> None:
        """Mark the collection as built by the current models (call after a full sync)."""
        await self.client.update_collection(self.collection, metadata=self._metadata())
        self._verified = False

    async def _verify(self) -> None:
        if self._verified:
            return
        if not await self.client.collection_exists(self.collection):
            raise KnowledgeUnavailable(
                f"collection {self.collection!r} does not exist yet: run `make ingest`"
            )
        info = await self.client.get_collection(self.collection)
        size = await self._dense_size()
        meta: dict[str, Any] = info.config.metadata or {}
        stored_model = meta.get("embedding_model")
        stored_sparse = meta.get("sparse_encoder")
        if size != self.embedder.dim or stored_model not in (None, self.embedder.model):
            raise IndexMismatch(
                f"the index was built with model {stored_model!r} ({size} dims) but this "
                f"server uses {self.embedder.model!r} ({self.embedder.dim} dims): re-ingest "
                "with `make ingest`"
            )
        if stored_sparse not in (None, self.sparse.name):
            raise IndexMismatch(
                f"the index was built with sparse encoder {stored_sparse!r} but this server "
                f"uses {self.sparse.name!r}: re-ingest with `make ingest`"
            )
        self._verified = True

    # --- sync primitives (used by ingest.sync_chunks) ---

    async def stored_points(self) -> dict[str, StoredPoint]:
        """Every point's chunk id, content hash and kb_version, keyed by point id."""
        out: dict[str, StoredPoint] = {}
        offset: Any = None
        while True:
            points, offset = await self.client.scroll(
                self.collection,
                limit=256,
                offset=offset,
                with_payload=["chunk_id", "content_hash", "kb_version"],
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                out[str(p.id)] = StoredPoint(
                    chunk_id=str(payload.get("chunk_id", "")),
                    content_hash=str(payload.get("content_hash", "")),
                    kb_version=str(payload.get("kb_version", "")),
                )
            if offset is None:
                return out

    async def upsert(
        self,
        chunks: list[Chunk],
        hashes: list[str],
        dense: list[list[float]],
        sparse: list[SparseVector],
        kb_version: str,
    ) -> None:
        points = [
            models.PointStruct(
                id=point_id(c.id),
                vector={
                    DENSE: d,
                    SPARSE: models.SparseVector(indices=s.indices, values=s.values),
                },
                payload={
                    "chunk_id": c.id,
                    "doc_id": c.doc_id,
                    "kind": c.kind,
                    "title": c.title,
                    "section": c.section,
                    "text": c.text,
                    "as_of": c.as_of.isoformat() if c.as_of else None,
                    "source": c.source,
                    "content_hash": h,
                    "kb_version": kb_version,
                },
            )
            for c, h, d, s in zip(chunks, hashes, dense, sparse, strict=True)
        ]
        await self.client.upsert(self.collection, points=points, wait=True)

    async def delete(self, point_ids: list[str]) -> None:
        await self.client.delete(
            self.collection, points_selector=models.PointIdsList(points=list(point_ids)), wait=True
        )

    async def set_kb_version(self, point_ids: list[str], kb_version: str) -> None:
        await self.client.set_payload(
            self.collection, payload={"kb_version": kb_version}, points=list(point_ids), wait=True
        )

    async def count(self) -> int:
        if not await self.client.collection_exists(self.collection):
            return 0
        return (await self.client.count(self.collection, exact=True)).count

    def remember_version(self, kb_version: str) -> None:
        self._kb_version = kb_version

    async def sync(self, chunks: list[Chunk]) -> SyncReport:
        return await sync_chunks(self, chunks)

    # --- search ---

    async def _embed_query(self, query: str) -> tuple[list[float], bool]:
        model, dim = self.embedder.model, self.embedder.dim
        if self._cache is not None:
            cached = await self._cache.get(model, query, dim)
            if cached is not None:
                return cached, True
        vector = await self.embedder.embed_query(query)
        if self._cache is not None:
            await self._cache.set(model, query, vector)
        return vector, False

    async def search(self, query: str, k: int = 4) -> SearchResult:
        await self._verify()
        t0 = time.perf_counter()
        dense, cache_hit = await self._embed_query(query)
        sparse = self.sparse.embed_query(query)
        t1 = time.perf_counter()
        sparse_q = models.SparseVector(indices=sparse.indices, values=sparse.values)
        fused, best = await asyncio.gather(
            self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=dense, using=DENSE, limit=PREFETCH_LIMIT),
                    models.Prefetch(query=sparse_q, using=SPARSE, limit=PREFETCH_LIMIT),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=k,
                with_payload=True,
            ),
            self.client.query_points(
                self.collection, query=dense, using=DENSE, limit=1, with_payload=False
            ),
        )
        t2 = time.perf_counter()

        hits = [_hit(p.payload or {}) for p in fused.points]
        if not hits and await self.count() == 0:
            raise KnowledgeUnavailable("the knowledge base is empty: run `make ingest`")
        best_score = best.points[0].score if best.points else None
        version = ""
        if fused.points:
            version = str((fused.points[0].payload or {}).get("kb_version", ""))
        version = version or self._kb_version or ""
        if version:
            self._kb_version = version
        return SearchResult(
            hits=hits,
            best_dense_score=best_score,
            no_match=not hits or best_score is None or best_score < self.min_score,
            kb_version=version,
            embed_ms=(t1 - t0) * 1000,
            search_ms=(t2 - t1) * 1000,
            query_cache_hit=cache_hit,
        )

    async def close(self) -> None:
        await self.client.close()


def _hit(payload: dict[str, Any]) -> Hit:
    return Hit(
        id=str(payload.get("chunk_id", "")),
        doc_id=str(payload.get("doc_id", "")),
        kind=str(payload.get("kind", "")),
        title=str(payload.get("title", "")),
        section=str(payload.get("section", "")),
        text=str(payload.get("text", "")),
        as_of=payload.get("as_of"),
        source=payload.get("source"),
    )


class UnavailableKnowledgeBase:
    """Stands in when the knowledge base cannot be built (no key, store locked, nothing ingested).

    The server still starts; every search raises KnowledgeUnavailable, which the tool turns
    into `kb_unavailable` and the recruiter hand-off.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def search(self, query: str, k: int = 4) -> SearchResult:
        raise KnowledgeUnavailable(self.reason)

    async def sync(self, chunks: list[Chunk]) -> SyncReport:
        raise KnowledgeUnavailable(self.reason)

    async def close(self) -> None:
        return None
