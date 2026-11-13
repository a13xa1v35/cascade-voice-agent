"""Knowledge-base startup never crashes the app: a missing key reports unavailable, and a
failed sync keeps serving the existing index."""

from pathlib import Path

import pytest
from knowledge_support import section, write_doc

from hr_screener.config import Settings
from hr_screener.knowledge.embeddings import (
    FakeEmbedder,
    FakeSparseEncoder,
)
from hr_screener.knowledge.service import open_knowledge_base
from hr_screener.knowledge.store import QdrantKnowledgeBase, UnavailableKnowledgeBase
from hr_screener.knowledge.types import (
    EmbeddingError,
    KnowledgeUnavailable,
)


@pytest.fixture
def kb_settings(tmp_path, monkeypatch) -> Settings:
    root = tmp_path / "knowledge"
    write_doc(root, "pagos", section("Tarifas por hora", 200, "tarifa"))
    # The real BM25 encoder would download a model: tests always use the fake.
    monkeypatch.setattr(
        "hr_screener.knowledge.service.make_sparse_encoder", lambda settings: FakeSparseEncoder()
    )
    return Settings(
        _env_file=None,
        kb_dir=str(root),
        qdrant_path=str(tmp_path / "qdrant"),
        fastembed_cache_dir=str(tmp_path / "fastembed"),
        openai_api_key="test-key",
    )


async def test_missing_api_key_reports_unavailable_without_raising(kb_settings):
    kb_settings.openai_api_key = ""
    kb = await open_knowledge_base(kb_settings)
    assert isinstance(kb, UnavailableKnowledgeBase)
    with pytest.raises(KnowledgeUnavailable, match="OPENAI_API_KEY"):
        await kb.search("hola", 4)
    await kb.close()


async def test_failed_sync_keeps_serving_an_existing_index(kb_settings):
    first = await open_knowledge_base(kb_settings, embedder=FakeEmbedder())
    await first.close()
    broken = FakeEmbedder(fail=EmbeddingError("voyage down"))
    write_doc(
        Path(kb_settings.kb_dir),
        "pagos",
        section("Tarifas por hora", 220, "nueva"),
    )
    kb = await open_knowledge_base(kb_settings, embedder=broken)
    assert isinstance(kb, QdrantKnowledgeBase)
    broken.fail = None
    assert (await kb.search("tarifas por hora", 2)).hits  # the old index still answers
    await kb.close()


# --- command line ---
