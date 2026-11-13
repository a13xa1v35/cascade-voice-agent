"""Build the knowledge base for the app, never failing the app.

`open_knowledge_base(settings)` is what the server calls once at startup. It builds the
embedder, the BM25 encoder and the Qdrant client from Settings, syncs KB_DIR when
KB_SYNC_ON_STARTUP is on, and returns a `KnowledgeBase`. Whatever goes wrong, it returns
one: when the knowledge base cannot work, an `UnavailableKnowledgeBase` whose `search` raises
`KnowledgeUnavailable`, which the tool reports as `kb_unavailable` (Sofia then refers the
question to a recruiter). The server starts either way.

* No API key for the hosted provider (OPENAI_API_KEY, or VOYAGE_API_KEY with voyage), a
  locked embedded folder, a BM25 model that cannot be loaded: unavailable, with the reason
  logged once.
* The sync fails (embedding provider down, bad markdown) but the collection already has
  points: keep serving the existing index and log a warning. Search itself checks that the
  index matches the configured models, so a half-migrated index is refused rather than served.
* The sync fails and the collection is empty: unavailable.
"""

import asyncio
import inspect
import logging

from redis.asyncio import Redis

from hr_screener.config import Settings
from hr_screener.knowledge.cache import QueryEmbeddingCache
from hr_screener.knowledge.chunking import load_chunks
from hr_screener.knowledge.embeddings import Embedder, make_embedder, make_sparse_encoder
from hr_screener.knowledge.store import (
    KnowledgeBase,
    QdrantKnowledgeBase,
    UnavailableKnowledgeBase,
    make_client,
)
from hr_screener.knowledge.types import KnowledgeError

log = logging.getLogger(__name__)


async def _warm_up(*parts: object) -> None:
    """Call `warm_up` on every part that has one: an async method, or a blocking one that
    runs in a thread."""
    for part in parts:
        warm = getattr(part, "warm_up", None)
        if warm is None:
            continue
        if inspect.iscoroutinefunction(warm):
            await warm()
        else:
            await asyncio.to_thread(warm)


async def open_knowledge_base(
    settings: Settings,
    *,
    redis: Redis | None = None,
    embedder: Embedder | None = None,
    sync: bool | None = None,
) -> KnowledgeBase:
    """`redis` enables the query embedding cache; `embedder` overrides the provider (tests);
    `sync` overrides KB_SYNC_ON_STARTUP."""
    try:
        embedder = embedder or make_embedder(settings)
        sparse = await asyncio.to_thread(make_sparse_encoder, settings)
        client = make_client(settings)
        # Load the models now, off the loop: a lazy ONNX load (or download) on the first live
        # search would eat the call-time deadline. Even when the sync is off or nothing changed.
        await _warm_up(embedder, sparse)
    except KnowledgeError as e:
        log.warning("knowledge base unavailable: %s", e)
        return UnavailableKnowledgeBase(str(e))
    except Exception as e:
        log.warning("knowledge base unavailable: %s: %s", type(e).__name__, e, exc_info=True)
        return UnavailableKnowledgeBase(f"{type(e).__name__}: {e}")

    kb = QdrantKnowledgeBase(
        client,
        embedder,
        sparse,
        collection=settings.qdrant_collection,
        min_score=settings.kb_min_score,
        cache=QueryEmbeddingCache(redis) if redis is not None else None,
        payload_index=bool(settings.qdrant_url),
    )
    if not (settings.kb_sync_on_startup if sync is None else sync):
        return kb
    try:
        report = await kb.sync(load_chunks(settings.kb_dir))
    except Exception as e:
        existing = 0
        try:
            existing = await kb.count()
        except Exception:
            log.debug("could not count points after a failed sync", exc_info=True)
        if existing:
            log.warning(
                "knowledge base sync failed (%s: %s); serving the existing index (%d points)",
                type(e).__name__,
                e,
                existing,
            )
            return kb
        log.warning(
            "knowledge base sync failed and the index is empty: %s: %s", type(e).__name__, e
        )
        await kb.close()
        return UnavailableKnowledgeBase(f"sync failed: {e}")
    log.info("knowledge base ready: %s", report)
    return kb
