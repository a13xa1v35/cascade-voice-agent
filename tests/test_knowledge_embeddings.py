"""Embedding vectors stay aligned with the chunks they belong to. Fake OpenAI client."""

from types import SimpleNamespace

import pytest

from hr_screener.knowledge.embeddings import OpenAIEmbedder
from hr_screener.knowledge.types import EmbeddingError


class FakeOpenAI:
    """Stands in for `AsyncOpenAI`: `embeddings.create` returns items in reverse order."""

    def __init__(self, *, drop: int = 0, error: Exception | None = None) -> None:
        self.embeddings = SimpleNamespace(create=self._create)
        self.calls: list[dict] = []
        self._drop = drop
        self._error = error

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        texts = kwargs["input"][: len(kwargs["input"]) - self._drop]
        # the vector's first value is the text's number, so tests can see the ordering
        data = [SimpleNamespace(index=i, embedding=[float(t), 0.0]) for i, t in enumerate(texts)]
        return SimpleNamespace(data=list(reversed(data)))


def make(client: FakeOpenAI, **kwargs) -> OpenAIEmbedder:
    embedder = OpenAIEmbedder("test-key", dim=2, **kwargs)
    embedder._client = client
    return embedder


async def test_vectors_are_ordered_by_index_and_model_and_dimensions_are_sent():
    client = FakeOpenAI()
    vectors = await make(client).embed_documents(["1", "2", "3"])
    assert vectors == [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]
    assert client.calls == [
        {"model": "text-embedding-3-large", "input": ["1", "2", "3"], "dimensions": 2}
    ]


async def test_a_vector_count_mismatch_is_an_embedding_error():
    with pytest.raises(EmbeddingError, match="1 vectors for 2 texts"):
        await make(FakeOpenAI(drop=1)).embed_documents(["1", "2"])
