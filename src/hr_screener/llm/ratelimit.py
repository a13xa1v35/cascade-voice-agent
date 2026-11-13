"""Client-side rate limiter for Sofia's LLM requests: a sliding 60 s window on requests and on
input tokens, shared by every call in the process.

It exists for quota-limited keys (a free tier, a quota shared with other services) and for the
eval, which fires many conversations at one key. A normal paid key does not need it, so it is
off unless `LLM_MAX_RPM` / `LLM_MAX_TPM` is set.

Trade-offs, all deliberate:

- It is per process. Several app instances sharing one quota would each stay under their own
  limit and together exceed the provider's; that needs a shared limiter (e.g. a Redis script).
- When the quota is the bottleneck it makes a live call wait: the request is held until it
  fits, so the candidate hears a longer silence. That is better than a 429 (the SDK retries,
  and a request that still fails leaves Sofia silent), but it is latency, not magic.
- Input tokens are estimated before the request (see `estimate_tokens`), not measured: the
  provider's real count is only known afterwards. Set `LLM_MAX_TPM` a little under the real
  limit. Retries the SDK makes after a 429 are not seen here either.
- Requests are admitted in arrival order. A request larger than the whole token budget is
  admitted when the window is empty (it can never fit, and waiting forever helps nobody).
"""

import asyncio
import json
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

WINDOW_SECS = 60.0
CHARS_PER_TOKEN = 4  # rough rule of thumb for English; Spanish runs a bit higher


def estimate_tokens(*parts: Any) -> int:
    """Cheap input-token estimate for a request: characters / 4 of the JSON form of `parts`
    (system prompt, tool schemas, messages). It ignores the previous request's real token
    count on purpose: that would need a hook into usage reporting, and the context only
    grows, so the estimate stays close enough for a limit that is set with some margin."""
    chars = sum(len(p) if isinstance(p, str) else len(json.dumps(p, default=str)) for p in parts)
    return chars // CHARS_PER_TOKEN + 1


class SlidingWindowLimiter:
    """Admits at most `max_rpm` requests and `max_tpm` tokens in any 60 s window.

    `clock` and `sleep` are injectable so tests can run it on a fake clock."""

    def __init__(
        self,
        max_rpm: float = 0,
        max_tpm: int = 0,
        *,
        name: str = "",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.name = name
        self._clock = clock
        self._sleep = sleep
        self._window: deque[tuple[float, int]] = deque()  # (admitted at, tokens)
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self.waited_secs = 0.0  # total time requests spent waiting, for logs and tests

    @property
    def enabled(self) -> bool:
        return self.max_rpm > 0 or self.max_tpm > 0

    def _get_lock(self) -> asyncio.Lock:
        # An asyncio.Lock belongs to one loop; the registry below outlives a loop in tests.
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock, self._lock_loop = asyncio.Lock(), loop
        return self._lock

    def _prune(self, now: float) -> None:
        while self._window and now - self._window[0][0] >= WINDOW_SECS:
            self._window.popleft()

    def _wait_needed(self, now: float, tokens: int) -> float:
        """Seconds until a request of `tokens` fits; 0 if it fits now."""
        if not self._window:
            return 0.0
        wait = 0.0
        if self.max_rpm > 0:
            capacity = max(1, int(self.max_rpm))
            over = len(self._window) + 1 - capacity
            if over > 0:  # the `over`-th oldest request has to leave the window
                wait = max(wait, self._window[over - 1][0] + WINDOW_SECS - now)
        if self.max_tpm > 0:
            used = sum(t for _, t in self._window)
            for admitted_at, freed in self._window:
                if used + tokens <= self.max_tpm:
                    break
                used -= freed
                wait = max(wait, admitted_at + WINDOW_SECS - now)
        return wait

    async def acquire(self, tokens: int = 0) -> float:
        """Wait until a request of `tokens` input tokens fits, record it, and return the
        seconds waited. Cancellation while waiting records nothing."""
        if not self.enabled:
            return 0.0
        started = self._clock()
        async with self._get_lock():  # first come, first served
            while True:
                now = self._clock()
                self._prune(now)
                wait = self._wait_needed(now, tokens)
                if wait <= 0:
                    self._window.append((now, tokens))
                    break
                logger.info(f"{self.name or 'llm'} rate limit: waiting {wait:.1f}s for a slot")
                await self._sleep(wait)
        waited = self._clock() - started
        self.waited_secs += waited
        return waited


_limiters: dict[tuple[str, str], SlidingWindowLimiter] = {}


def get_limiter(provider: str, model: str, max_rpm: float, max_tpm: int) -> SlidingWindowLimiter:
    """The process-wide limiter for a provider and model (quotas are per model). Calls share
    it, so concurrent conversations count against one budget. Changing the limits for a key
    that already has a limiter updates it in place."""
    key = (provider, model)
    limiter = _limiters.get(key)
    if limiter is None:
        limiter = _limiters[key] = SlidingWindowLimiter(
            max_rpm, max_tpm, name=f"{provider}/{model}"
        )
    limiter.max_rpm, limiter.max_tpm = max_rpm, max_tpm
    return limiter


def reset_limiters() -> None:
    """Forget every limiter (tests)."""
    _limiters.clear()
