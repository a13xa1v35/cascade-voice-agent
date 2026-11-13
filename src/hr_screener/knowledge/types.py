"""Result and error types shared by the knowledge-base modules.

Plain frozen dataclasses: they cross the boundary to the search tool (later phase), which
turns them into the JSON the model reads. Nothing here depends on Qdrant or an embedding
provider, so the other modules can import it without cycles.
"""

from dataclasses import dataclass


class KnowledgeError(Exception):
    """Base class for every error this package raises on purpose."""


class KnowledgeBaseContentError(KnowledgeError):
    """The markdown source is invalid (front matter, duplicate ids, empty directory)."""


class KnowledgeUnavailable(KnowledgeError):
    """The knowledge base cannot answer now (no key, empty index, store down).

    The search tool maps it to `kb_unavailable`, so the caller can offer the fallback.
    """


class IndexMismatch(KnowledgeUnavailable):
    """The stored index was built with another embedding model or dimension."""


class StoreLocked(KnowledgeError):
    """Embedded Qdrant's folder is already open in another process."""


class EmbeddingError(KnowledgeError):
    """An embedding call failed (network, rate limit that outlasted the retries, bad key)."""


@dataclass(frozen=True)
class Hit:
    """One retrieved chunk, in fused-ranking order."""

    id: str  # chunk id, "{doc_id}#{section-slug}"
    doc_id: str
    kind: str  # "policy" | "regulation"
    title: str
    section: str
    text: str  # what the model reads (without the context header)
    as_of: str | None  # ISO date, regulation only
    source: str | None


@dataclass(frozen=True)
class SearchResult:
    hits: list[Hit]
    # Best dense cosine score over the whole collection. Fused (RRF) scores are rank-based
    # and not comparable across queries, so the "no match" decision uses this one.
    best_dense_score: float | None
    no_match: bool
    kb_version: str
    embed_ms: float  # query embedding (or the cache lookup)
    search_ms: float  # the Qdrant queries
    query_cache_hit: bool = False


@dataclass(frozen=True)
class SyncReport:
    added: int
    updated: int
    deleted: int
    unchanged: int
    kb_version: str
    embed_calls: int  # calls to Embedder.embed_documents (0 when nothing changed)

    def __str__(self) -> str:
        return (
            f"added={self.added} updated={self.updated} deleted={self.deleted} "
            f"unchanged={self.unchanged} embed_calls={self.embed_calls} "
            f"kb_version={self.kb_version[:12]}"
        )
