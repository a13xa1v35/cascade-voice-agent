"""Cross-call memory: continue a screening that failed or was left unfinished.

A new call for a candidate whose previous call dropped (FAILED), asked for a callback or
never picked up is linked to it (`previous_screening_id`, `attempt + 1`) and starts with
the previous facts already on file, so the record_* tools and the qualification rule
work unchanged. Calls that reached a final outcome (scheduled, not
qualified, not interested, wrong person) start fresh, with two exceptions: a candidate who is
booked or was rejected is *closed* (see `CallMode`): the next call only informs them and
never screens them again.

A stale start date does not travel: a carried `start_date` before today is cleared in the
store, so the qualification rule and `missing_questions` see the question as unanswered.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from loguru import logger

from hr_screener.config import Settings
from hr_screener.models import (
    CallSummary,
    Candidate,
    Channel,
    OnboardingSlot,
    Outcome,
    ReferredQuestion,
    Screening,
    ScreeningFacts,
    ScreeningStatus,
)
from hr_screener.storage.store import ScreeningStore

# Outcomes that leave the screening open: the candidate still has to be (re)reached.
_OPEN_OUTCOMES = frozenset({Outcome.CALLBACK_REQUESTED, Outcome.NO_ANSWER})


async def default_candidate(store: ScreeningStore, settings: Settings) -> Candidate | None:
    """The candidate a web or terminal call uses when none is named: DEMO_CANDIDATE_ID, else
    the most recent one. A configured id this database does not know (a `.env` copied between
    checkouts, each with its own database) warns and falls back instead of failing."""
    if settings.demo_candidate_id:
        if candidate := await store.get_candidate(settings.demo_candidate_id):
            return candidate
        logger.warning(
            f"DEMO_CANDIDATE_ID {settings.demo_candidate_id!r} is not in this database; "
            "using the most recent candidate"
        )
    return await store.most_recent_candidate()


class CallMode(StrEnum):
    """What kind of call a screening is. Decided once, from the stored history (see
    `load_call_context`); the bot, the prompt and the tools all read it."""

    FRESH = "fresh"  # a first screening
    FOLLOWUP = "followup"  # continues an unfinished one, facts carried over
    CLOSED_BOOKED = "closed_booked"  # already booked: inform, answer, no screening
    CLOSED_REJECTED = "closed_rejected"  # rejected: polite close, no screening

    @property
    def is_closed(self) -> bool:
        return self in (CallMode.CLOSED_BOOKED, CallMode.CLOSED_REJECTED)


class EndedHow(StrEnum):
    DROPPED = "dropped"  # the call was cut, went idle or crashed
    CALLBACK_REQUESTED = "callback_requested"
    NO_ANSWER = "no_answer"


@dataclass(frozen=True)
class FollowUpContext:
    previous_screening_id: str
    attempt: int  # of the call being started
    previous_at: datetime  # when the previous call started
    ended: EndedHow
    callback_note: str | None  # what the candidate said about when to call back
    summary: CallSummary | None
    facts: ScreeningFacts
    # The start date the previous call recorded but that had passed by now (so it was
    # cleared and must be asked again); None when there was none or it is still valid.
    stale_start_date: date | None = None
    # Questions already referred to a recruiter in earlier calls of the chain (all rows,
    # automatic or not), so this call neither asks nor promises them again.
    referred_questions: tuple[ReferredQuestion, ...] = ()

    @property
    def interest_confirmed(self) -> bool:
        """The earlier call got past the interest check: the screening questions come after
        it, so any saved answer means the candidate said they are interested and had time."""
        f = self.facts
        return bool(
            f.start_date
            or f.subjects
            or f.availability
            or f.teaching_format is not None
            or f.work_authorized is not None
            or f.experience
            or self.stale_start_date
        )

    def is_recent(self, now: datetime, minutes: int) -> bool:
        """The earlier call started at most `minutes` before `now` (timezone-aware)."""
        return now - self.previous_at <= timedelta(minutes=minutes)


@dataclass(frozen=True)
class ClosedContext:
    """The decision a closed-mode call is about."""

    decided_screening_id: str
    outcome: Outcome  # SCHEDULED or NOT_QUALIFIED
    decided_at: datetime
    slot: OnboardingSlot | None  # the booked onboarding session (SCHEDULED only)

    def session_passed(self, now: datetime) -> bool:
        """True when the booked session started before `now` (timezone-aware). Attendance is
        not tracked, so this is all that is known about a past session. It is a question
        about the clock, not stored state: callers pass one `now` for the whole call so the
        prompt and the opening message always agree."""
        return self.slot is not None and self.slot.starts_at < now


@dataclass(frozen=True)
class CallContext:
    """Everything the bot needs to know about the call it is starting."""

    mode: CallMode
    followup: FollowUpContext | None = None
    closed: ClosedContext | None = None


def local_today(timezone: str) -> date:
    """Today's date in the given IANA timezone (callers pass `Settings.timezone`)."""
    return datetime.now(ZoneInfo(timezone)).date()


def _is_decisive(screening: Screening) -> bool:
    """Scheduled (with a booking) or not qualified: the candidate is closed. Policy: not
    interested / wrong person are deliberately not decisive, the next call screens afresh
    (add them here to close those candidates too)."""
    if screening.outcome is Outcome.SCHEDULED:
        return screening.slot_id is not None
    return screening.outcome is Outcome.NOT_QUALIFIED


async def decisive_screening(store: ScreeningStore, candidate_id: str) -> Screening | None:
    """The newest screening of the candidate that decided their case, or None.

    Walks the whole history rather than looking at the latest screening: after a closed-mode
    call (outcome already_screened, or failed) the latest one is no longer the decision."""
    for screening in await store.list_screenings(candidate_id):
        if _is_decisive(screening):
            return screening
    return None


def is_resumable(screening: Screening) -> bool:
    """FAILED (dropped / idle / crash), or ended asking for a callback / with no answer.
    A final outcome wins over the status; calls still running are never resumable."""
    if screening.outcome is not None:
        return screening.outcome in _OPEN_OUTCOMES
    return screening.status is ScreeningStatus.FAILED


async def _resumable_previous(store: ScreeningStore, candidate_id: str) -> Screening | None:
    for screening in await store.list_screenings(candidate_id):
        if screening.status is ScreeningStatus.PENDING:
            continue  # created but nobody ever connected: carries no information
        return screening if is_resumable(screening) else None
    return None


async def new_screening(
    store: ScreeningStore,
    candidate: Candidate,
    channel: Channel,
    *,
    today: date,
    resume: bool = True,
    status: ScreeningStatus = ScreeningStatus.PENDING,
) -> Screening:
    """Create the candidate's next screening.

    - A closed candidate (booked / rejected, see `decisive_screening`) gets a closed-mode
      screening linked to the deciding one, `attempt` = deciding attempt + 1 (the invariant
      "attempt = previous + 1 when linked" holds), no facts. This runs first and ignores
      `resume`: such a screening is never resumable, so it can never leak into a follow-up.
    - Otherwise it continues the previous one when that is resumable (and `resume` is true),
      copying its facts forward; a carried start date before `today` is cleared.
    - Otherwise it is a fresh screening.
    `today` is the date in the call timezone (`local_today(settings.timezone)`)."""
    decided = await decisive_screening(store, candidate.id)
    if decided is not None:
        return await store.create_screening(
            Screening(
                candidate_id=candidate.id,
                channel=channel,
                status=status,
                previous_screening_id=decided.id,
                attempt=decided.attempt + 1,
            )
        )
    previous = await _resumable_previous(store, candidate.id) if resume else None
    if previous is None:
        return await store.create_screening(
            Screening(candidate_id=candidate.id, channel=channel, status=status)
        )
    screening = await store.create_screening(
        Screening(
            candidate_id=candidate.id,
            channel=channel,
            status=status,
            previous_screening_id=previous.id,
            attempt=previous.attempt + 1,
        )
    )
    await store.copy_facts(previous.id, screening.id)
    carried = (await store.get_facts(screening.id)).start_date
    if carried is not None and carried < today:
        await store.clear_start_date(screening.id)  # evaluate() reads the stored facts
    return screening


async def load_call_context(store: ScreeningStore, screening: Screening) -> CallContext:
    """The mode of the call being started, from how `new_screening` linked it."""
    if not screening.previous_screening_id:
        return CallContext(CallMode.FRESH)
    previous = await store.get_screening(screening.previous_screening_id)
    if previous is None:
        return CallContext(CallMode.FRESH)
    if previous.outcome is not None and _is_decisive(previous):
        slot = await store.get_slot(previous.slot_id) if previous.slot_id else None
        closed = ClosedContext(previous.id, previous.outcome, previous.created_at, slot)
        booked = previous.outcome is Outcome.SCHEDULED
        mode = CallMode.CLOSED_BOOKED if booked else CallMode.CLOSED_REJECTED
        return CallContext(mode, closed=closed)
    followup = await load_followup(store, screening)
    return CallContext(CallMode.FOLLOWUP if followup else CallMode.FRESH, followup=followup)


async def load_followup(store: ScreeningStore, screening: Screening) -> FollowUpContext | None:
    """What the prompt needs to continue the previous call; None for a first call (and for
    a closed-mode call, which continues nothing)."""
    if not screening.previous_screening_id:
        return None
    previous = await store.get_screening(screening.previous_screening_id)
    if previous is None or _is_decisive(previous):
        return None
    if previous.outcome is Outcome.CALLBACK_REQUESTED:
        ended = EndedHow.CALLBACK_REQUESTED
    elif previous.outcome is Outcome.NO_ANSWER or not await store.get_transcript(previous.id):
        ended = EndedHow.NO_ANSWER  # nobody spoke (also a call that never connected)
    else:
        ended = EndedHow.DROPPED
    facts = await store.get_facts(screening.id)  # carried over, and any since
    previous_start = (await store.get_facts(previous.id)).start_date
    return FollowUpContext(
        previous_screening_id=previous.id,
        attempt=screening.attempt,
        previous_at=previous.created_at,
        ended=ended,
        callback_note=previous.notes if ended is EndedHow.CALLBACK_REQUESTED else None,
        summary=await store.get_summary(previous.id),
        facts=facts,
        # Carried on the previous call but gone from this one: new_screening cleared it.
        stale_start_date=previous_start if facts.start_date is None else None,
        referred_questions=await _chain_referred_questions(store, previous),
    )


async def _chain_referred_questions(
    store: ScreeningStore, previous: Screening
) -> tuple[ReferredQuestion, ...]:
    """The questions referred to a recruiter in every earlier attempt of the chain
    (`previous`, the one before it, ...), most recent attempt first: a hand-off made on
    attempt 1 still stands on attempt 3."""
    found: list[ReferredQuestion] = []
    seen: set[str] = set()
    screening: Screening | None = previous
    while screening is not None and screening.id not in seen:
        seen.add(screening.id)
        found += await store.list_referred_questions(screening_id=screening.id)
        screening = (
            await store.get_screening(screening.previous_screening_id)
            if screening.previous_screening_id
            else None
        )
    return tuple(found)
