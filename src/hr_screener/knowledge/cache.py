"""Optional Redis cache for query embeddings.

Spoken questions rarely repeat word for word, so the hit rate will be modest, but a hit
saves a network round trip on the call's critical path and costs one GET. The cache is an
optimisation only: with no Redis (`None`) or a Redis error, search embeds the query itself.
Keys include the model, so changing the embedding model never serves stale vectors.
"""

import hashlib
import json
import logging
from typing import Any

from redis.asyncio import Redis

log = logging.getLogger(__name__)

TTL_SECS = 24 * 3600


class QueryEmbeddingCache:
    def __init__(self, redis: Redis, ttl_secs: int = TTL_SECS) -> None:
        # Any for the same reason as ScreeningStore.redis: redis-py's stubs are noisy.
        # The client must be created with decode_responses=True.
        self._redis: Any = redis
        self._ttl = ttl_secs

    @staticmethod
    def key(model: str, query: str) -> str:
        return f"kb:qemb:{model}:{hashlib.sha256(query.encode()).hexdigest()}"

    async def get(self, model: str, query: str, dim: int) -> list[float] | None:
        try:
            raw = await self._redis.get(self.key(model, query))
            if raw is None:
                return None
            vector = json.loads(raw)
        except Exception:
            log.warning("query embedding cache read failed", exc_info=True)
            return None
        if not isinstance(vector, list) or len(vector) != dim:
            return None
        return [float(x) for x in vector]

    async def set(self, model: str, query: str, vector: list[float]) -> None:
        try:
            await self._redis.set(self.key(model, query), json.dumps(vector), ex=self._ttl)
        except Exception:
            log.warning("query embedding cache write failed", exc_info=True)
