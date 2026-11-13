"""Live-call registry: lets a new call for a candidate end the one still running.

A candidate cannot be on two calls. When their browser drops, the server may not notice for
~30 s (SmallWebRTC only errors the media stream then), and the candidate often reconnects
before that. Without this, the old screening is still `in_progress` (not resumable), so the
new call would start from scratch. `supersede_live_call` ends the old call first, so that
`followup.new_screening` finds it `failed` and resumes from its facts.

The registry is per process: it only knows the calls this server instance runs. With several
app instances, superseding a call that lives on another instance would need a cross-instance
signal (Redis pub/sub, or a lease/heartbeat column on the screening). Until then a call that
is `in_progress` but not registered here is closed by a status compare-and-set instead.
"""

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

from hr_screener.models import Candidate, Channel, Screening, ScreeningStatus
from hr_screener.screening.followup import local_today, new_screening
from hr_screener.storage.store import ScreeningStore

ABANDONED_NOTE = "abandoned: superseded by a new call"


class LiveCall:
    """One running call. `bot.py` binds how to stop it and sets `status_final` once the
    final status is written (not after the summary, which can take 30 s)."""

    def __init__(self, screening_id: str) -> None:
        self.screening_id = screening_id
        self.status_final = asyncio.Event()
        self.end_requested = False
        self._stop: Callable[[], Awaitable[None]] | None = None

    def bind_stop(self, stop: Callable[[], Awaitable[None]]) -> None:
        """Set once the pipeline runner exists (before that, `end` only records the request
        and the bot checks `end_requested` before starting)."""
        self._stop = stop

    async def end(self) -> None:
        self.end_requested = True
        if self._stop is not None:
            await self._stop()


class LiveCalls:
    def __init__(self) -> None:
        self._calls: dict[str, LiveCall] = {}

    def register(self, screening_id: str) -> LiveCall:
        call = self._calls[screening_id] = LiveCall(screening_id)
        return call

    def unregister(self, screening_id: str) -> None:
        self._calls.pop(screening_id, None)

    def get(self, screening_id: str) -> LiveCall | None:
        return self._calls.get(screening_id)

    def __contains__(self, screening_id: str) -> bool:
        return screening_id in self._calls


async def _last_started(store: ScreeningStore, candidate_id: str) -> Screening | None:
    """The candidate's newest screening that someone connected to (same rule as
    `followup._resumable_previous`: a `pending` one carries no information)."""
    for screening in await store.list_screenings(candidate_id):
        if screening.status is not ScreeningStatus.PENDING:
            return screening
    return None


async def _close_abandoned(store: ScreeningStore, screening_id: str) -> bool:
    """in_progress -> failed by compare-and-set, so a finalize that wins the race (and may
    have inferred an outcome) is never overwritten."""
    if not await store.transition_status(
        screening_id, ScreeningStatus.IN_PROGRESS, ScreeningStatus.FAILED
    ):
        return False
    await store.update_screening(screening_id, notes=ABANDONED_NOTE)
    return True


async def supersede_live_call(
    store: ScreeningStore,
    live_calls: LiveCalls | None,
    candidate_id: str,
    wait_secs: float,
) -> None:
    """Call before creating a new screening for `candidate_id`: if their latest screening is
    still `in_progress` it is dead (they cannot be on two calls), so end it. Returns once it
    is no longer in progress."""
    previous = await _last_started(store, candidate_id)
    if previous is None or previous.status is not ScreeningStatus.IN_PROGRESS:
        return

    live = live_calls.get(previous.id) if live_calls else None
    if live is None:
        # Server restarted mid-call or the task died: nothing will ever finalize it.
        if await _close_abandoned(store, previous.id):
            logger.info(f"[{previous.id}] in progress but not live here: closed as abandoned")
        return

    logger.info(f"[{previous.id}] superseded by a new call for candidate {candidate_id}")

    async def end_and_wait() -> None:
        await live.end()
        await live.status_final.wait()

    try:
        await asyncio.wait_for(end_and_wait(), wait_secs)  # the stop itself is bounded too
    except TimeoutError:
        logger.warning(f"[{previous.id}] did not finalize within {wait_secs}s: forcing it closed")
    except Exception:
        logger.exception(f"[{previous.id}] could not end the live call: forcing it closed")
    await _close_abandoned(store, previous.id)  # no-op when finalize already wrote the status


async def start_screening(
    store: ScreeningStore,
    live_calls: LiveCalls,
    candidate: Candidate,
    *,
    channel: Channel,
    timezone: str,
    supersede_wait_secs: float,
) -> Screening:
    """The same steps as the browser's POST /start + offer: end a live call of the candidate,
    create the next screening (a follow-up when the last one is resumable) and claim it
    (pending -> in_progress). Shared by the terminal chat and the eval harness."""
    await supersede_live_call(store, live_calls, candidate.id, supersede_wait_secs)
    screening = await new_screening(
        store, candidate, channel, today=local_today(timezone), resume=True
    )
    if not await store.transition_status(
        screening.id, ScreeningStatus.PENDING, ScreeningStatus.IN_PROGRESS
    ):
        raise RuntimeError(f"screening {screening.id} was already claimed")
    return screening
