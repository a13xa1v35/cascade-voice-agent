"""The index never serves stale or mismatched vectors: syncs are idempotent, edits and
deletions reach the index, a model change re-embeds, and a model or dimension mismatch refuses
to search. In-memory Qdrant with fake embedders; no model downloads, no network."""

import json
from typing import cast

import pytest
from knowledge_support import make_kb, section, words, write_doc
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from hr_screener.knowledge.cache import QueryEmbeddingCache
from hr_screener.knowledge.chunking import load_chunks
from hr_screener.knowledge.embeddings import FakeEmbedder, FakeSparseEncoder
from hr_screener.knowledge.store import QdrantKnowledgeBase
from hr_screener.knowledge.types import (
    IndexMismatch,
)


@pytest.fixture
def kb_dir(tmp_path):
    root = tmp_path / "knowledge"
    write_doc(
        root,
        "pagos",
        section("Tarifas por hora", 200, "tarifa") + section("Calendario de pagos", 200, "pago"),
        title="Pagos y tarifas",
    )
    write_doc(
        root,
        "irpf",
        "## Retenciones de IRPF\n\nlas retenciones de irpf en las facturas de clases "
        + words(190, "irpf")
        + "\n",
        kind="regulation",
        title="Retenciones",
    )
    return root


async def payloads(kb: QdrantKnowledgeBase) -> dict[str, dict]:
    points, _ = await kb.client.scroll(kb.collection, limit=100, with_payload=True)
    return {str(p.payload["chunk_id"]): dict(p.payload) for p in points if p.payload}


# --- sync ---


async def test_second_sync_makes_no_embedding_calls(kb_dir):
    embedder = FakeEmbedder()
    kb = make_kb(embedder)
    first = await kb.sync(load_chunks(kb_dir))
    calls = embedder.document_calls
    second = await kb.sync(load_chunks(kb_dir))
    assert embedder.document_calls == calls
    assert (second.added, second.updated, second.deleted, second.unchanged) == (0, 0, 0, 3)
    assert second.embed_calls == 0
    assert second.kb_version == first.kb_version


async def test_edit_replaces_the_point_and_changes_kb_version(kb_dir):
    embedder = FakeEmbedder()
    kb = make_kb(embedder)
    first = await kb.sync(load_chunks(kb_dir))
    write_doc(
        kb_dir,
        "pagos",
        section("Tarifas por hora", 210, "nueva") + section("Calendario de pagos", 200, "pago"),
        title="Pagos y tarifas",
    )
    texts_before = embedder.texts_embedded
    second = await kb.sync(load_chunks(kb_dir))
    assert (second.added, second.updated, second.deleted, second.unchanged) == (0, 1, 0, 2)
    assert embedder.texts_embedded == texts_before + 1
    assert second.kb_version != first.kb_version
    stored = await payloads(kb)
    assert len(stored) == 3  # replaced, not duplicated
    assert "nueva0" in stored["pagos#tarifas-por-hora"]["text"]
    # Unchanged points carry the new version too.
    assert {p["kb_version"] for p in stored.values()} == {second.kb_version}


async def test_removed_document_deletes_its_points(kb_dir):
    kb = make_kb()
    first = await kb.sync(load_chunks(kb_dir))
    (kb_dir / "irpf.md").unlink()
    second = await kb.sync(load_chunks(kb_dir))
    assert (second.added, second.updated, second.deleted, second.unchanged) == (0, 0, 1, 2)
    assert second.kb_version != first.kb_version
    assert "irpf#retenciones-de-irpf" not in await payloads(kb)


async def test_changing_the_model_reembeds_everything(kb_dir):
    client = AsyncQdrantClient(":memory:")
    chunks = load_chunks(kb_dir)
    a = QdrantKnowledgeBase(client, FakeEmbedder(model="m1"), FakeSparseEncoder())
    await a.sync(chunks)
    b = QdrantKnowledgeBase(client, FakeEmbedder(model="m2"), FakeSparseEncoder())
    report = await b.sync(chunks)
    assert report.updated == 3
    assert report.embed_calls == 1


# --- search ---


# --- compatibility ---


async def test_dimension_mismatch_refuses_to_search(kb_dir):
    client = AsyncQdrantClient(":memory:")
    await QdrantKnowledgeBase(client, FakeEmbedder(dim=64), FakeSparseEncoder()).sync(
        load_chunks(kb_dir)
    )
    other = QdrantKnowledgeBase(client, FakeEmbedder(dim=96), FakeSparseEncoder())
    with pytest.raises(IndexMismatch, match="re-ingest"):
        await other.search("tarifas", k=2)


async def test_model_mismatch_refuses_to_search(kb_dir):
    client = AsyncQdrantClient(":memory:")
    await QdrantKnowledgeBase(client, FakeEmbedder(model="m1"), FakeSparseEncoder()).sync(
        load_chunks(kb_dir)
    )
    other = QdrantKnowledgeBase(client, FakeEmbedder(model="m2"), FakeSparseEncoder())
    with pytest.raises(IndexMismatch, match=r"'m1'.*'m2'.*re-ingest"):
        await other.search("tarifas", k=2)


# --- query embedding cache ---


async def test_cache_survives_garbage_and_redis_errors(redis):
    cache = QueryEmbeddingCache(redis)
    await redis.set(QueryEmbeddingCache.key("m", "q"), "not json")
    assert await cache.get("m", "q", 2) is None
    await redis.set(QueryEmbeddingCache.key("m", "q"), json.dumps({"a": 1}))
    assert await cache.get("m", "q", 2) is None

    class Down:
        async def get(self, key):
            raise ConnectionError("redis is down")

        set = get

    broken = QueryEmbeddingCache(cast(Redis, Down()))
    assert await broken.get("m", "q", 2) is None
    await broken.set("m", "q", [1.0])  # must not raise
