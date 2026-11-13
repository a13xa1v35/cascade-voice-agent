"""Disk cache and accounting around an `Embedder`, so reruns of the eval cost nothing.

Vectors are keyed by model + dimension (one JSON file per pair), kind (document or query) and
sha256 of the text. Tokens are counted by wrapping the client's call (Voyage `embed`, OpenAI
`embeddings.create`), because the embedders themselves throw the usage away.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hr_screener.knowledge.embeddings import Embedder

DEFAULT_CACHE_DIR = Path("var/kb_eval_cache")  # `var/` is git-ignored


@dataclass
class EmbedStats:
    texts_embedded: int = 0  # texts that went to the model / API (cache misses)
    cache_hits: int = 0
    api_calls: int = 0
    tokens: int = 0  # provider-reported tokens; 0 when none
    chars: int = 0  # characters of the embedded texts


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CachedEmbedder:
    def __init__(self, inner: Embedder, cache_dir: Path | None = DEFAULT_CACHE_DIR) -> None:
        self.inner = inner
        self.model = inner.model
        self.dim = inner.dim
        self.stats = EmbedStats()
        self._path: Path | None = None
        self._vectors: dict[str, list[float]] = {}
        self._dirty = False
        if cache_dir is not None:
            slug = re.sub(r"[^A-Za-z0-9._-]+", "_", self.model)
            self._path = Path(cache_dir) / f"{slug}-{self.dim}.json"
            if self._path.exists():
                self._vectors = json.loads(self._path.read_text(encoding="utf-8"))
        self._hook_usage(inner)

    def _hook_usage(self, inner: Any) -> None:
        client = getattr(inner, "_client", None)
        if client is None:
            return
        if callable(getattr(client, "embed", None)):  # Voyage: result.total_tokens
            target, name = client, "embed"
        elif callable(getattr(getattr(client, "embeddings", None), "create", None)):
            target, name = client.embeddings, "create"  # OpenAI: result.usage.total_tokens
        else:
            return
        original = getattr(target, name)

        async def counting(*args: Any, **kwargs: Any) -> Any:
            result = await original(*args, **kwargs)
            self.stats.api_calls += 1
            usage = getattr(result, "usage", None)
            tokens = getattr(result, "total_tokens", None) or getattr(usage, "total_tokens", 0)
            self.stats.tokens += int(tokens or 0)
            return result

        setattr(target, name, counting)

    def flush(self) -> None:
        if self._path is None or not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._vectors), encoding="utf-8")
        tmp.replace(self._path)
        self._dirty = False

    async def _embed(self, texts: list[str], kind: str) -> list[list[float]]:
        keys = [f"{kind}:{_sha(t)}" for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self._vectors]
        self.stats.cache_hits += len(texts) - len(missing)
        if missing:
            todo = [texts[i] for i in missing]
            if kind == "q":
                vectors = [await self.inner.embed_query(t) for t in todo]
            else:
                vectors = await self.inner.embed_documents(todo)
            for i, vec in zip(missing, vectors, strict=True):
                self._vectors[keys[i]] = vec
            self.stats.texts_embedded += len(todo)
            self.stats.chars += sum(len(t) for t in todo)
            self._dirty = True
            if kind == "d":
                self.flush()  # queries are flushed by the runner, once, at the end
        return [self._vectors[k] for k in keys]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "d")

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "q"))[0]
