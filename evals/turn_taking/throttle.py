"""Global session-start throttle and retry helper (AssemblyAI caps new sessions per minute)."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable


class StartThrottle:
    """Sliding-window limiter: at most `max_starts` acquisitions in any `window` seconds."""

    def __init__(
        self,
        max_starts: int,
        window: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.max_starts = max_starts
        self.window = window
        self._clock = clock
        self._sleep = sleep
        self._starts: deque[float] = deque()
        self._lock = asyncio.Lock()  # waiters queue up in order

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                while self._starts and now - self._starts[0] >= self.window:
                    self._starts.popleft()
                if len(self._starts) < self.max_starts:
                    self._starts.append(now)
                    return
                await self._sleep(self._starts[0] + self.window - now)


async def with_retries[T](
    attempt: Callable[[], Awaitable[T]],
    *,
    should_retry: Callable[[Exception], bool],
    max_retries: int,
    wait_secs: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    for n in range(max_retries + 1):
        try:
            return await attempt()
        except Exception as e:
            if n >= max_retries or not should_retry(e):
                raise
            if on_retry:
                on_retry(n + 1, e)
            await sleep(wait_secs)
    raise AssertionError("unreachable")
