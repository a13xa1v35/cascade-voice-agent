"""Cross-call memory: which earlier screening a new call continues, and the guarantee that a
candidate whose screening is decided (booked or rejected) is never screened again, including
when the call history cannot be loaded."""

from datetime import UTC, date, datetime, timedelta

import pytest
from textcall_helpers import new_call
from tool_call import Call

from hr_screener import i18n
from hr_screener.agent.tools import ToolDeps
from hr_screener.config import Settings
from hr_screener.i18n import LANGS
from hr_screener.models import (
    Availability,
    Candidate,
    Channel,
    Level,
    OnboardingSlot,
    Opening,
    Outcome,
    Screening,
    ScreeningFacts,
    ScreeningStatus,
    SlotMode,
    Subject,
    TeachingFormat,
)
from hr_screener.pipeline import bot
from hr_screener.pipeline.bot import _finish_status, load_call_context_safe
from hr_screener.screening.followup import (
    CallMode,
    decisive_screening,
    is_resumable,
    load_call_context,
    new_screening,
)
from hr_screener.storage.store import ScreeningStore

S = ScreeningStatus
O = Outcome  # noqa: E741
T0 = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)
TODAY = T0.date()  # passed explicitly to new_screening: no real clock involved

FACTS = ScreeningFacts(
    start_date=date(2026, 11, 16),
    subjects=[Subject.MATH, Subject.PHYSICS],
    levels=[Level.SECONDARY, Level.UPPER_SECONDARY],
    work_authorized=True,
)  # schedule (availability + format) and experience are still missing


@pytest.fixture
async def candidate(store: ScreeningStore, opening: Opening) -> Candidate:
    return await store.create_candidate(
        Candidate(name="Maria Lopez", phone="+34600", location="Madrid", opening_id=opening.id)
    )


async def seed_call(
    store: ScreeningStore,
    candidate: Candidate,
    status: ScreeningStatus,
    outcome: Outcome | None = None,
) -> Screening:
    """A past screening with FACTS recorded and a one-line transcript."""
    screening = await store.create_screening(
        Screening(
            candidate_id=candidate.id,
            channel=Channel.WEBRTC,
            status=status,
            outcome=outcome,
            created_at=T0,
        )
    )
    assert FACTS.start_date is not None and FACTS.work_authorized is not None
    await store.set_start_date(screening.id, FACTS.start_date)
    await store.set_subjects(screening.id, FACTS.subjects)
    await store.set_levels(screening.id, FACTS.levels)
    await store.set_work_authorized(screening.id, FACTS.work_authorized)
    await store.save_transcript(screening.id, [{"role": "assistant", "text": "Hi"}])
    return screening


async def booked(store: ScreeningStore, candidate: Candidate) -> Screening:
    """A finished screening that booked an onboarding slot."""
    screening = await seed_call(store, candidate, S.COMPLETED, O.SCHEDULED)
    slot = await store.create_slot(
        OnboardingSlot(
            starts_at=datetime.now(UTC) + timedelta(days=2),
            mode=SlotMode.IN_PERSON,
            address="Chamberí, Madrid",
        )
    )
    await store.book_slot(screening.id, slot.id)
    return screening


async def open_call(store: ScreeningStore, candidate: Candidate) -> Screening:
    return await new_screening(store, candidate, Channel.WEBRTC, today=TODAY)


# --- resumable vs final ---


@pytest.mark.parametrize(
    ("status", "outcome", "resumable"),
    [
        (S.FAILED, None, True),
        (S.COMPLETED, O.CALLBACK_REQUESTED, True),
        (S.COMPLETED, O.SCHEDULED, False),
        (S.COMPLETED, O.NOT_INTERESTED, False),
        (S.IN_PROGRESS, None, False),
    ],
)
async def test_which_calls_are_continued(
    store: ScreeningStore,
    candidate: Candidate,
    status: ScreeningStatus,
    outcome: Outcome | None,
    resumable: bool,
):
    previous = await seed_call(store, candidate, status, outcome)
    assert is_resumable(previous) is resumable
    new = await open_call(store, candidate)
    if resumable:
        assert new.previous_screening_id == previous.id and new.attempt == 2
    else:
        assert new.previous_screening_id is None and new.attempt == 1
        assert await store.get_facts(new.id) == ScreeningFacts()


async def test_facts_are_copied_forward_and_the_original_is_untouched(
    store: ScreeningStore, candidate: Candidate
):
    previous = await seed_call(store, candidate, S.FAILED)
    new = await open_call(store, candidate)
    assert await store.get_facts(new.id) == FACTS  # the list tables came along too

    await store.set_work_authorized(new.id, False)
    await store.set_subjects(new.id, [Subject.CHEMISTRY])
    await store.set_levels(new.id, [Level.UNIVERSITY])
    await store.set_availability(new.id, [Availability.SATURDAY_MORNING])
    await store.set_teaching_format(new.id, TeachingFormat.ONLINE)
    assert await store.get_facts(previous.id) == FACTS


# --- a decided candidate is never screened again ---


async def test_the_decision_is_found_after_a_closed_mode_call(store, candidate):
    decided = await booked(store, candidate)
    closed_call = await open_call(store, candidate)
    await store.finish_screening(closed_call.id, S.COMPLETED, O.ALREADY_SCREENED, "asked to cancel")
    assert (await store.latest_screening(candidate.id)).id == closed_call.id
    found = await decisive_screening(store, candidate.id)
    assert found is not None and found.id == decided.id

    again = await open_call(store, candidate)
    assert again.previous_screening_id == decided.id
    assert (await load_call_context(store, again)).mode is CallMode.CLOSED_BOOKED


async def test_a_closed_mode_call_without_end_call_is_never_resumed(store, candidate):
    decided = await booked(store, candidate)
    closed_call = await open_call(store, candidate)
    await store.update_screening(closed_call.id, status=S.IN_PROGRESS.value)
    await store.save_transcript(closed_call.id, [{"role": "assistant", "text": "Hi Maria"}])
    # the candidate hangs up: no end_call, so the status is inferred
    await _finish_status(closed_call.id, store, Settings(_env_file=None, timezone="UTC"))
    dropped = await store.get_screening(closed_call.id)
    assert dropped.status is S.FAILED and dropped.outcome is None
    assert is_resumable(dropped)  # on its own it would qualify as a follow-up ...

    nxt = await open_call(store, candidate)  # ... but the closed check comes first
    assert nxt.previous_screening_id == decided.id
    assert await store.get_facts(nxt.id) == ScreeningFacts()
    assert (await load_call_context(store, nxt)).mode is CallMode.CLOSED_BOOKED


@pytest.mark.parametrize("outcome", ["scheduled", "not_qualified"])
async def test_closed_end_call_rejects_other_outcomes(store, settings, candidate, outcome):
    await booked(store, candidate)
    screening = await open_call(store, candidate)
    await store.update_screening(screening.id, status=S.IN_PROGRESS.value)
    mode = CallMode.CLOSED_BOOKED
    call = Call(ToolDeps(store=store, screening_id=screening.id, settings=settings, mode=mode))
    await call.run("end_call", outcome=outcome)
    assert "error" in call.result
    assert (await store.get_screening(screening.id)).outcome is None
    assert call.llm.pushed == []  # the call does not end


# --- the call history cannot be loaded: fail closed ---


async def test_a_missing_previous_screening_is_a_fresh_call_but_a_failed_lookup_is_not(
    store: ScreeningStore, candidate: Candidate
):
    screening = Screening(candidate_id=candidate.id, channel=Channel.WEBRTC, attempt=2)
    broken = screening.model_copy(update={"previous_screening_id": "gone"})
    ctx = await load_call_context_safe(store, broken)
    assert ctx is not None and ctx.mode is CallMode.FRESH  # gone: nothing to continue

    class Boom(ScreeningStore):
        async def get_screening(self, screening_id: str):
            raise RuntimeError("redis down")

    # Fail closed: None, never a FRESH context that would re-screen a booked candidate.
    assert await load_call_context_safe(Boom(store.engine, store.redis), broken) is None


@pytest.mark.parametrize("lang", LANGS)
async def test_failed_lookup_apologizes_and_ends_without_the_llm(
    store, text_settings, candidate, monkeypatch, lang
):
    settings = text_settings.model_copy(update={"language": lang})
    made: list = []

    async def boom(store, screening):
        raise RuntimeError("database down")

    monkeypatch.setattr(bot, "load_call_context", boom)
    monkeypatch.setattr(bot, "make_llm", lambda *a, **k: made.append(1))
    decided = await booked(store, candidate)  # must NOT be re-screened
    screening = await open_call(store, candidate)
    await store.update_screening(screening.id, status=S.IN_PROGRESS.value)

    async with new_call(store, settings, screening) as call:
        assert await call.next_reply(10) == i18n.context_unavailable_apology(lang)
        assert await call.next_reply(10) is None
        await call.wait_done()

    assert made == []  # no LLM was even built, so no LLM call and no tool
    done = await store.get_screening(screening.id)
    assert (done.status, done.outcome, done.slot_id) == (S.FAILED, None, None)
    assert await store.get_tool_calls(screening.id) == []
    assert is_resumable(done)
    assert (await store.get_screening(decided.id)).slot_id is not None  # booking untouched
