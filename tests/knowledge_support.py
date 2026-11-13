"""Helpers shared by the tests/test_knowledge_*.py modules (not a test module)."""

import asyncio
from pathlib import Path
from typing import Any

from qdrant_client import AsyncQdrantClient

from hr_screener.knowledge.embeddings import FakeEmbedder, FakeSparseEncoder
from hr_screener.knowledge.store import QdrantKnowledgeBase
from hr_screener.knowledge.types import Hit, SearchResult


def words(n: int, prefix: str = "palabra") -> str:
    """n distinct-ish words, so a section has an exact size."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def write_doc(
    root: Path,
    name: str,
    body: str,
    *,
    id: str | None = None,
    kind: str = "policy",
    title: str = "Pagos y tarifas",
    extra: str = "",
) -> Path:
    """A markdown file with front matter; regulation docs get as_of and source."""
    meta = [f"id: {id or name}", f"kind: {kind}", f"title: {title}"]
    if kind == "regulation":
        meta += ["as_of: 2026-01-01", "source: https://example.org/norma"]
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(meta) + f"\n{extra}---\n{body}\n", encoding="utf-8")
    return path


def section(heading: str, n_words: int, prefix: str | None = None) -> str:
    return f"## {heading}\n\n{words(n_words, prefix or heading.split()[0].lower())}\n\n"


def make_kb(
    embedder: FakeEmbedder | None = None, *, min_score: float = 0.5, cache=None
) -> QdrantKnowledgeBase:
    return QdrantKnowledgeBase(
        AsyncQdrantClient(":memory:"),
        embedder or FakeEmbedder(),
        FakeSparseEncoder(),
        min_score=min_score,
        cache=cache,
    )


def hit(id: str = "retenciones-irpf#nuevos", **kw: Any) -> Hit:
    base = {
        "id": id,
        "doc_id": id.split("#")[0],
        "kind": "regulation",
        "title": "Retenciones de IRPF",
        "section": "Nuevos profesionales",
        "text": "El porcentaje baja al 7 por ciento los tres primeros años.",
        "as_of": "2026-01-01",
        "source": "https://sede.example/irpf",
    }
    return Hit(**{**base, **kw})


def result(hits: list[Hit] | None = None, *, no_match: bool = False) -> SearchResult:
    return SearchResult(
        hits=[hit()] if hits is None else hits,
        best_dense_score=0.71,
        no_match=no_match,
        kb_version="v1",
        embed_ms=120.0,
        search_ms=4.0,
        query_cache_hit=False,
    )


class FakeKB:
    """Answers `search` with `outcome` (a result, or an exception to raise) after `delay`."""

    def __init__(self, outcome: SearchResult | Exception | None = None, delay: float = 0) -> None:
        self.outcome = result() if outcome is None else outcome
        self.delay = delay
        self.queries: list[tuple[str, int]] = []

    async def search(self, query: str, k: int) -> SearchResult:
        self.queries.append((query, k))
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def sync(self, chunks):  # pragma: no cover - protocol
        raise NotImplementedError

    async def close(self) -> None:
        pass
