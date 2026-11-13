"""Setup hooks: scenarios that start from database state instead of a first conversation.

Each hook builds the history the scenario needs (a failed screening with facts, a booked
candidate, a rejected one) straight in the store, which saves a whole conversation of tokens.
Facts come from the persona card so the simulated candidate stays consistent with what is on
file. A hook that fakes a dropped call also stores a short transcript: without one the next
call would be treated as "nobody picked up" instead of "we got cut off" (see
`followup.load_followup`).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from evals.e2e.persona import Persona, resolve_date
from hr_screener.config import Settings
from hr_screener.models import (
    Availability,
    Candidate,
    Channel,
    Level,
    OnboardingSlot,
    Outcome,
    Screening,
    ScreeningStatus,
    SlotMode,
    Subject,
    TeachingFormat,
)
from hr_screener.storage.store import ScreeningStore

_FAKE_TRANSCRIPT = {
    "es": [
        ("assistant", "Hola, soy Sofia de TuTeacher. ¿Hablo con {first_name}?"),
        ("user", "Sí, soy yo."),
        (
            "assistant",
            "Genial. Te llamo por tu solicitud como profesor particular. ¿Sigues interesado?",
        ),
        ("user", "Sí, claro."),
    ],
    "en": [
        (
            "assistant",
            "Hi, this is Sofia from TuTeacher. Am I speaking with {first_name}?",
        ),
        ("user", "Yes, that's me."),
        ("assistant", "Great. I'm calling about your tutor application. Are you still interested?"),
        ("user", "Yes, of course."),
    ],
}


@dataclass
class SetupContext:
    store: ScreeningStore
    settings: Settings
    candidate: Candidate
    persona: Persona
    today: date


class SetupFn(Protocol):
    async def __call__(self, ctx: SetupContext) -> None: ...


async def _save_facts(ctx: SetupContext, screening_id: str, start_date: date | None) -> None:
    p, store = ctx.persona, ctx.store
    if start_date is not None:
        await store.set_start_date(screening_id, start_date)
    await store.set_subjects(screening_id, [Subject(s) for s in p.subjects])
    await store.set_levels(screening_id, [Level(v) for v in p.levels])
    await store.set_availability(screening_id, [Availability(a) for a in p.availability])
    await store.set_teaching_format(screening_id, TeachingFormat(p.teaching_format))
    await store.set_work_authorized(screening_id, p.work_authorized)
    await store.set_experience(screening_id, p.experience)


async def _previous_screening(
    ctx: SetupContext, status: ScreeningStatus, outcome: Outcome | None = None
) -> Screening:
    screening = await ctx.store.create_screening(
        Screening(candidate_id=ctx.candidate.id, channel=Channel.TEXT, status=status)
    )
    turns = [
        {"role": role, "text": text.format(first_name=ctx.candidate.first_name)}
        for role, text in _FAKE_TRANSCRIPT[ctx.settings.language]
    ]
    await ctx.store.save_transcript(screening.id, turns)
    if outcome is not None:
        await ctx.store.finish_screening(screening.id, status, outcome, "eval setup")
    return screening


async def failed_all_facts_stale_start(ctx: SetupContext) -> None:
    """k: a dropped call that has every fact, but the start date it recorded was yesterday."""
    screening = await _previous_screening(ctx, ScreeningStatus.FAILED)
    await _save_facts(ctx, screening.id, resolve_date("yesterday", ctx.today))


async def booked_candidate(ctx: SetupContext) -> None:
    """l1: a candidate who qualified and has a booked onboarding session."""
    screening = await _previous_screening(ctx, ScreeningStatus.IN_PROGRESS)
    await _save_facts(ctx, screening.id, ctx.persona.start_date(ctx.today))
    tz = ZoneInfo(ctx.settings.timezone)
    slot = (await ctx.store.list_open_slots(datetime.now(tz) + timedelta(hours=1), limit=1))[0]
    await ctx.store.book_slot(screening.id, slot.id)
    await ctx.store.finish_screening(
        screening.id, ScreeningStatus.COMPLETED, Outcome.SCHEDULED, "eval setup"
    )


async def booked_candidate_session_passed(ctx: SetupContext) -> None:
    """l3: like l1, but the onboarding session was yesterday. Seeded slots are all in the
    future, so this creates its own (booking does not look at the clock)."""
    screening = await _previous_screening(ctx, ScreeningStatus.IN_PROGRESS)
    await _save_facts(ctx, screening.id, ctx.persona.start_date(ctx.today))
    tz = ZoneInfo(ctx.settings.timezone)
    starts_at = (datetime.now(tz) - timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    slot = await ctx.store.create_slot(
        OnboardingSlot(starts_at=starts_at, mode=SlotMode.ONLINE, capacity=5)
    )
    await ctx.store.book_slot(screening.id, slot.id)
    await ctx.store.finish_screening(
        screening.id, ScreeningStatus.COMPLETED, Outcome.SCHEDULED, "eval setup"
    )


async def rejected_candidate(ctx: SetupContext) -> None:
    """l2: a candidate the rule rejected (the persona is not authorized to work)."""
    screening = await _previous_screening(ctx, ScreeningStatus.IN_PROGRESS)
    await _save_facts(ctx, screening.id, ctx.persona.start_date(ctx.today))
    await ctx.store.finish_screening(
        screening.id, ScreeningStatus.COMPLETED, Outcome.NOT_QUALIFIED, "eval setup"
    )
