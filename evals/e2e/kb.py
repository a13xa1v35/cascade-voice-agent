"""Knowledge bases for the e2e scenarios.

Three kinds, picked per scenario (`KbSpec`):

* `real`: the app's own `QdrantKnowledgeBase` over `knowledge/`, in an in-memory Qdrant,
  built once per run by `KbHub` and shared by every conversation. Vectors go through the
  eval-kb disk cache (`evals/kb/embed_cache.py`), so a rerun embeds nothing. It uses the
  configured `KB_MIN_SCORE` (unlike the retrieval eval, which turns the threshold off),
  because the out-of-scope scenario needs a real `no_match`.
* `slow`: the real index behind a sleep, to force the deferred path (the candidate keeps
  talking while the search runs and the result arrives late).
* `down`: `UnavailableKnowledgeBase`, which raises `KnowledgeUnavailable` on every search,
  so the tool answers `kb_unavailable` and Sofia refers the question to a recruiter.

Scenarios without a spec get no knowledge base at all: the knowledge tools and prompt section
are not offered, exactly as before (`bot.run_screening_bot`: `knowledge is None`).
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from qdrant_client import AsyncQdrantClient

from evals.kb.embed_cache import DEFAULT_CACHE_DIR, CachedEmbedder, EmbedStats
from hr_screener.config import Settings
from hr_screener.knowledge.chunking import Chunk, load_chunks
from hr_screener.knowledge.embeddings import (
    Embedder,
    SparseEncoder,
    make_embedder,
    make_sparse_encoder,
)
from hr_screener.knowledge.store import (
    KnowledgeBase,
    QdrantKnowledgeBase,
    UnavailableKnowledgeBase,
)
from hr_screener.knowledge.types import SearchResult, SyncReport

KbMode = Literal["real", "slow", "down"]

# How long the slow knowledge base sleeps before it searches. It must outlast a candidate
# line plus Sofia's reply to it (a simulator call and an LLM turn, a few seconds), and stay
# under the search deadline, or the slow search becomes a `kb_unavailable` one:
# `settings_for` raises the deadlines above it for the conversation.
SLOW_DELAY_SECS = 10.0
DEADLINE_MARGIN_SECS = 15.0


@dataclass(frozen=True)
class KbSpec:
    mode: KbMode
    delay_secs: float = 0.0  # slow only


class SlowKnowledgeBase:
    """Sleeps `delay_secs`, then delegates the search. `sync` and `close` are the owner's:
    the hub shares one index between conversations, so a conversation never closes it."""

    def __init__(
        self,
        inner: KnowledgeBase,
        delay_secs: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.inner = inner
        self.delay_secs = delay_secs
        self._sleep = sleep

    async def search(self, query: str, k: int) -> SearchResult:
        await self._sleep(self.delay_secs)
        return await self.inner.search(query, k)

    async def sync(self, chunks: list[Chunk]) -> SyncReport:
        return await self.inner.sync(chunks)

    async def close(self) -> None:
        return None


def down_knowledge_base() -> UnavailableKnowledgeBase:
    """A knowledge base whose every search raises `KnowledgeUnavailable`."""
    return UnavailableKnowledgeBase("eval: knowledge base down")


def settings_for(spec: KbSpec | None, settings: Settings) -> Settings:
    """The conversation's settings: for a slow knowledge base the search deadlines are moved
    above the delay (the defaults, 5 s and 8 s, would time the slow search out)."""
    if spec is None or spec.mode != "slow":
        return settings
    return settings.model_copy(
        update={
            "kb_timeout_secs": max(
                settings.kb_timeout_secs, spec.delay_secs + DEADLINE_MARGIN_SECS
            ),
            "kb_tool_timeout_secs": max(
                settings.kb_tool_timeout_secs, spec.delay_secs + DEADLINE_MARGIN_SECS + 5
            ),
        }
    )


class KbHub:
    """Builds the real index lazily, once, and hands it to the conversations."""

    def __init__(
        self,
        settings: Settings,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        *,
        embedder: Embedder | None = None,
        sparse: SparseEncoder | None = None,
    ) -> None:
        self.settings = settings
        self.cache_dir = cache_dir
        self._embedder = embedder
        self._sparse = sparse
        self._lock = asyncio.Lock()
        self._real: QdrantKnowledgeBase | None = None
        self._chunks: dict[str, Chunk] | None = None
        self.cached: CachedEmbedder | None = None

    @property
    def chunks(self) -> dict[str, Chunk]:
        """Every chunk of KB_DIR by id (read from disk; no embedding)."""
        if self._chunks is None:
            self._chunks = {c.id: c for c in load_chunks(self.settings.kb_dir)}
        return self._chunks

    async def real(self) -> QdrantKnowledgeBase:
        """The shared index. Raises `KnowledgeError` (no key, bad markdown) to the caller."""
        async with self._lock:
            if self._real is None:
                inner = self._embedder or make_embedder(self.settings)
                sparse = self._sparse or await asyncio.to_thread(make_sparse_encoder, self.settings)
                self.cached = CachedEmbedder(inner, self.cache_dir)
                kb = QdrantKnowledgeBase(
                    AsyncQdrantClient(":memory:"),  # never the app's locked QDRANT_PATH
                    self.cached,
                    sparse,
                    collection=self.settings.qdrant_collection,
                    min_score=self.settings.kb_min_score,
                )
                await kb.sync(list(self.chunks.values()))
                self.cached.flush()
                self._real = kb
            return self._real

    async def knowledge(self, spec: KbSpec) -> KnowledgeBase:
        if spec.mode == "down":
            return down_knowledge_base()
        real = await self.real()
        return SlowKnowledgeBase(real, spec.delay_secs) if spec.mode == "slow" else real

    def chunk_info(self, ids: set[str]) -> dict[str, dict[str, Any]]:
        """What the model was shown for these chunks (`tools._search_payload`)."""
        info: dict[str, dict[str, Any]] = {}
        for cid in sorted(ids):
            chunk = self.chunks.get(cid)
            if chunk is not None:
                info[cid] = {
                    "title": chunk.title,
                    "kind": chunk.kind,
                    "as_of": chunk.as_of.isoformat() if chunk.as_of else None,
                    "text": chunk.text,
                }
        return info

    def stats(self) -> EmbedStats | None:
        return self.cached.stats if self.cached else None

    def describe(self) -> str:
        """One line for the report: provider, model, chunks and embedding work."""
        if self.cached is None:
            return "knowledge base: not built"
        s = self.cached.stats
        return (
            f"knowledge base: provider `{self.settings.embedding_provider}`, model "
            f"`{self.cached.model}`, {len(self.chunks)} chunks, min score "
            f"{self.settings.kb_min_score}; embeddings: {s.texts_embedded} embedded, "
            f"{s.cache_hits} cache hits, {s.tokens} embedding tokens"
        )

    async def close(self) -> None:
        if self.cached is not None:
            self.cached.flush()  # queries embedded during the run
        if self._real is not None:
            await self._real.close()
