"""Dense and sparse text encoders behind small protocols.

Dense vectors capture meaning (and, with a multilingual model, cross-language matches);
sparse BM25 vectors capture exact terms (RETA, IRPF, *modelo 130*), which embeddings often
miss. Hybrid search needs both, and both sides must be produced by the same models at
ingestion and at query time, so the model identity is part of every chunk's content hash.

* `Embedder`: `OpenAIEmbedder` (default) and `VoyageEmbedder` (both network calls),
  `LocalEmbedder` (fastembed ONNX model, run in a worker thread so the event loop never
  blocks) and `FakeEmbedder` (hashed bag of words, deterministic, for tests).
* `SparseEncoder`: `Bm25Encoder` (fastembed `Qdrant/bm25` with the knowledge base language's
  stemmer and stopwords) and `FakeSparseEncoder`.

Heavy imports (fastembed pulls onnxruntime) happen inside the constructors, so importing
this module stays cheap and tests that use the fakes never load a model. Real models are
built once at startup (`service.open_knowledge_base`), never lazily inside a call: the first
use downloads files, which must not happen while someone is on the phone.
"""

import asyncio
import hashlib
import math
import re
import unicodedata
import zlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from hr_screener.config import Settings
from hr_screener.knowledge.types import EmbeddingError, KnowledgeUnavailable

# fastembed's names for the languages we support (KB_LANGUAGE -> BM25 stemmer/stopwords).
BM25_LANGUAGES = {"es": "spanish", "en": "english"}


class Embedder(Protocol):
    model: str  # identity of the vectors; part of every content hash
    dim: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]
    values: list[float]


class SparseEncoder(Protocol):
    name: str  # identity of the vectors, e.g. "Qdrant/bm25:spanish"

    def embed_documents(self, texts: list[str]) -> list[SparseVector]: ...
    def embed_query(self, text: str) -> SparseVector: ...


# --- OpenAI ---


class OpenAIEmbedder:
    """OpenAI embeddings (`text-embedding-3-large` shortened to 1024 dims by default).

    OpenAI has no document / query input types: documents and queries are embedded the
    same way, so there is nothing to tell the model apart. `dimensions` shortens the vector
    server side (the `text-embedding-3` models only). Rate limits, 5xx errors and timeouts
    are retried by the client (exponential backoff, up to `max_retries` attempts); anything
    that still fails is raised as EmbeddingError.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        dim: int = 1024,
        *,
        batch_size: int = 128,
        max_retries: int = 5,
        timeout: float = 30.0,
    ) -> None:
        import openai

        self.model = model
        self.dim = dim
        self._batch_size = batch_size
        self._client: Any = openai.AsyncOpenAI(
            api_key=api_key, max_retries=max_retries, timeout=timeout
        )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAIError

        try:
            result = await self._client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dim
            )
        except OpenAIError as e:
            raise EmbeddingError(f"OpenAI embedding failed: {e}") from e
        # The API returns one item per input with its position; do not rely on list order.
        items = sorted(result.data, key=lambda item: item.index)
        vectors: list[list[float]] = [[float(x) for x in item.embedding] for item in items]
        if len(vectors) != len(texts):
            raise EmbeddingError(f"OpenAI returned {len(vectors)} vectors for {len(texts)} texts")
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            out.extend(await self._embed(texts[i : i + self._batch_size]))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]


# --- Voyage ---


class VoyageEmbedder:
    """Voyage AI embeddings (`voyage-4-lite`, 1024 dims by default).

    Documents and queries use `input_type` "document" / "query": Voyage prepends a different
    instruction to each, which is what makes retrieval work well. Rate limits, 503s and
    timeouts are retried by the client (exponential backoff with jitter, up to `max_retries`
    attempts); anything that still fails is raised as EmbeddingError.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "voyage-4-lite",
        dim: int = 1024,
        *,
        batch_size: int = 64,
        max_retries: int = 5,
        timeout: float = 30.0,
    ) -> None:
        import voyageai

        self.model = model
        self.dim = dim
        self._batch_size = batch_size
        self._client: Any = voyageai.AsyncClient(
            api_key=api_key, max_retries=max_retries, timeout=timeout
        )

    async def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        from voyageai.error import VoyageError

        try:
            result = await self._client.embed(
                texts, model=self.model, input_type=input_type, output_dimension=self.dim
            )
        except VoyageError as e:
            raise EmbeddingError(f"Voyage embedding failed: {e}") from e
        vectors: list[list[float]] = [list(v) for v in result.embeddings]
        if len(vectors) != len(texts):
            raise EmbeddingError(f"Voyage returned {len(vectors)} vectors for {len(texts)} texts")
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            out.extend(await self._embed(texts[i : i + self._batch_size], "document"))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "query"))[0]


# --- Local (fastembed) ---


class LocalEmbedder:
    """A multilingual ONNX model through fastembed: no network, no key, lower quality.

    Inference runs in a worker thread (`asyncio.to_thread`). The model loads on first use,
    inside that thread; `warm_up` forces it at startup.
    """

    def __init__(
        self,
        model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        *,
        cache_dir: str | None = None,
        batch_size: int = 32,
    ) -> None:
        from fastembed import TextEmbedding

        known = {m["model"]: m["dim"] for m in TextEmbedding.list_supported_models()}
        if model not in known:
            raise KnowledgeUnavailable(f"fastembed does not support embedding model {model!r}")
        self.model = model
        self.dim: int = known[model]
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._impl: Any = None

    def _load(self) -> Any:
        if self._impl is None:
            from fastembed import TextEmbedding

            self._impl = TextEmbedding(self.model, cache_dir=self._cache_dir)
        return self._impl

    def _embed_sync(self, texts: list[str], query: bool) -> list[list[float]]:
        impl = self._load()
        gen = impl.query_embed(texts) if query else impl.embed(texts, batch_size=self._batch_size)
        return [[float(x) for x in v] for v in gen]

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._load)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts, False)

    async def embed_query(self, text: str) -> list[float]:
        return (await asyncio.to_thread(self._embed_sync, [text], True))[0]


# --- Fakes (tests) ---

_TOKEN = re.compile(r"\w+")


def _tokens(text: str) -> list[str]:
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return _TOKEN.findall(plain.lower())


@dataclass
class FakeEmbedder:
    """Deterministic hashed bag of words, L2-normalised.

    Texts that share words get a high cosine score and unrelated texts a low one, so search
    tests exercise real ranking. Not multilingual. Counts its calls for assertions.
    """

    model: str = "fake-embedder"
    dim: int = 128
    document_calls: int = 0
    query_calls: int = 0
    texts_embedded: int = 0
    fail: Exception | None = field(default=None, repr=False)

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokens(text):
            h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
            vec[h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
            vec[(h >> 8) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise self.fail
        self.document_calls += 1
        self.texts_embedded += len(texts)
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        if self.fail:
            raise self.fail
        self.query_calls += 1
        return self._vector(text)


# --- Sparse (BM25) ---


class Bm25Encoder:
    """fastembed `Qdrant/bm25` with the knowledge base language's stemmer and stopwords.

    The collection's `bm25` vector uses Qdrant's IDF modifier: fastembed computes term
    frequencies, the server multiplies by inverse document frequency at query time.
    """

    def __init__(self, language: str = "es", *, cache_dir: str | None = None) -> None:
        from fastembed import SparseTextEmbedding

        if language not in BM25_LANGUAGES:
            raise KnowledgeUnavailable(
                f"unsupported KB_LANGUAGE {language!r} (expected {', '.join(BM25_LANGUAGES)})"
            )
        bm25_language = BM25_LANGUAGES[language]
        self.name = f"Qdrant/bm25:{bm25_language}"
        self._impl: Any = SparseTextEmbedding(
            "Qdrant/bm25", cache_dir=cache_dir, language=bm25_language
        )

    @staticmethod
    def _convert(e: Any) -> SparseVector:
        return SparseVector([int(i) for i in e.indices], [float(v) for v in e.values])

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._convert(e) for e in self._impl.embed(texts)]

    def embed_query(self, text: str) -> SparseVector:
        return self._convert(next(iter(self._impl.query_embed(text))))


class FakeSparseEncoder:
    """Lowercase, accent-stripped words hashed to indices; the value is the term count."""

    name = "fake-sparse"

    @staticmethod
    def _encode(text: str) -> SparseVector:
        counts: dict[int, float] = {}
        for token in _tokens(text):
            idx = zlib.crc32(token.encode()) % (1 << 20)
            counts[idx] = counts.get(idx, 0.0) + 1.0
        return SparseVector(list(counts), list(counts.values()))

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._encode(t) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._encode(text)


# --- Factories ---


def make_embedder(settings: Settings) -> Embedder:
    """The embedder chosen by EMBEDDING_PROVIDER.

    Raises KnowledgeUnavailable when it cannot be built (openai or voyage without a key, an
    unknown local model); the app turns that into "knowledge base unavailable", not a crash.
    """
    if settings.embedding_provider == "local":
        return LocalEmbedder(settings.local_embedding_model, cache_dir=settings.fastembed_cache_dir)
    model = settings.effective_embedding_model
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise KnowledgeUnavailable("OPENAI_API_KEY is not set")
        return OpenAIEmbedder(settings.openai_api_key, model, settings.embedding_dim)
    if not settings.voyage_api_key:
        raise KnowledgeUnavailable("VOYAGE_API_KEY is not set")
    return VoyageEmbedder(settings.voyage_api_key, model, settings.embedding_dim)


def make_sparse_encoder(settings: Settings) -> SparseEncoder:
    return Bm25Encoder(settings.kb_language, cache_dir=settings.fastembed_cache_dir)
