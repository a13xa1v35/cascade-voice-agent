"""No candidate question is lost: `_finalize` leaves a running search or an unanswered
search that did not answer the candidate (`no_match`, `kb_unavailable`) and was not referred
to a recruiter. The knowledge base is a fake."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from hr_screener.agent.prompts import build_system_prompt
from hr_screener.agent.tools import SearchState, ToolDeps, build_tools
from hr_screener.config import Settings
from hr_screener.models import (
    Candidate,
    Opening,
    Outcome,
    ReferredQuestion,
    Role,
    Screening,
    ScreeningStatus,
    Subject,
)
from hr_screener.observability.observers import CallObservers
from hr_screener.pipeline import bot
from hr_screener.screening.followup import CallMode, ClosedContext
from hr_screener.storage.store import ScreeningStore


@pytest.fixture
async def deps(store: ScreeningStore, settings: Settings, opening: Opening) -> ToolDeps:
    candidate = await store.create_candidate(
        Candidate(name="Jo Doe", phone="+1555", location="Madrid", opening_id=opening.id)
    )
    screening = await store.create_screening(
        Screening(candidate_id=candidate.id, channel="webrtc", status=ScreeningStatus.IN_PROGRESS)
    )
    return ToolDeps(store=store, screening_id=screening.id, settings=settings)


# --- search_knowledge ----------------------------------------------------------------------


# --- refer_to_recruiter --------------------------------------------------------------------


# --- end_call ------------------------------------------------------------------------------


# --- tool offer ----------------------------------------------------------------------------


def names(mode: CallMode = CallMode.FRESH, **kw: Any) -> list[str]:
    return [t.name for t in build_tools(mode, **kw)[0].standard_tools]


# --- prompt --------------------------------------------------------------------------------


OPENING = Opening(role=Role.TUTOR, location="Madrid", subjects=[Subject.MATH])
CANDIDATE = Candidate(
    name="Maria Lopez",
    phone="+34",
    location="Madrid",
    opening_id=OPENING.id,
    subjects=[Subject.MATH],
)
BOOKED = ClosedContext("s0", Outcome.SCHEDULED, datetime(2026, 11, 6, tzinfo=UTC), None)


def prompt(settings: Settings, *, closed: ClosedContext | None = None, **kw: Any) -> str:
    return build_system_prompt(CANDIDATE, OPENING, settings, closed=closed, **kw)


# --- metrics -------------------------------------------------------------------------------


# --- _finalize: the questions nobody answered ------------------------------------------------


async def finalize(store, settings, screening_id, search: SearchState) -> CallObservers:
    observers = CallObservers(screening_id, redis=store.redis)
    await bot._finalize(
        screening_id,
        store,
        settings,
        None,
        observers,
        summarizer=_no_summary,
        search=search,
    )
    return observers


async def _no_summary(*args: Any):
    raise RuntimeError("no summary in this test")


async def test_finalize_leaves_a_running_search_to_a_recruiter(store, settings, deps):
    state = SearchState()
    state.begin("modelo 130 plazos")  # the call ended before the answer came back
    observers = await finalize(store, settings, deps.screening_id, state)

    (row,) = await store.list_referred_questions(screening_id=deps.screening_id)
    assert (row.question, row.automatic) == ("modelo 130 plazos", True)
    referred = [e for e in observers.recorder.events if e["type"] == "question_referred"]
    assert [e["data"]["automatic"] for e in referred] == [True]
    # it reached the stored timeline too (the event is recorded before the final flush)
    stored = json.loads((await store.redis.lrange(observers.recorder.key, 0, -1))[0])
    assert stored["type"] in {"question_referred", "call.ended"}
    card = await store.get_call_metrics(deps.screening_id)
    assert card is not None and card.knowledge is not None
    assert card.knowledge.questions_referred == 1


async def test_finalize_saves_unreferred_searches_and_leaves_referred_ones_to_the_agent(
    store, settings, deps
):
    state = SearchState()
    state.begin("verifactu")
    state.end(answered=False)  # kb_unavailable: Sofia never referred it
    state.begin("tarifa autonomos")
    state.end(answered=False)  # no_match, and Sofia called refer_to_recruiter
    await store.create_referred_question(
        ReferredQuestion(
            screening_id=deps.screening_id,
            question="tarifa plana",
            automatic=False,
            language=settings.language,
        )
    )
    state.resolve_latest()
    await finalize(store, settings, deps.screening_id, state)
    rows = await store.list_referred_questions(screening_id=deps.screening_id)
    assert sorted((r.question, r.automatic) for r in rows) == [
        ("tarifa plana", False),
        ("verifactu", True),
    ]
