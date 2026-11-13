"""Guards the tools enforce whatever the model does: no past start date, no non-boolean work
authorization, the verdict reads what was confirmed on the call, and no booking for a
candidate who does not qualify."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from tool_call import Call

from hr_screener.agent import tools
from hr_screener.agent.tools import ToolDeps
from hr_screener.config import Settings
from hr_screener.models import (
    Candidate,
    OnboardingSlot,
    Opening,
    Screening,
    ScreeningStatus,
    SlotMode,
    Subject,
)
from hr_screener.storage.store import ScreeningStore


@pytest.fixture
async def deps(store: ScreeningStore, settings: Settings, opening: Opening) -> ToolDeps:
    candidate = await store.create_candidate(
        Candidate(
            name="Jo Doe",
            phone="+1555",
            location="Madrid",
            opening_id=opening.id,
            subjects=[Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE],
        )
    )
    screening = await store.create_screening(
        Screening(candidate_id=candidate.id, channel="webrtc", status=ScreeningStatus.IN_PROGRESS)
    )
    return ToolDeps(store=store, screening_id=screening.id, settings=settings)


async def record(deps: ToolDeps, tool: str, **arguments: Any) -> Call:
    call = Call(deps)
    await call.run(tool, **arguments)
    return call


def good_arguments(*, authorized: bool = True) -> dict[str, dict[str, Any]]:
    """The arguments of every record_* tool, for a candidate who qualifies."""
    # The settings timezone is UTC; the tool compares the start date with today there.
    start = datetime.now(UTC).date() + timedelta(days=2)
    return {
        "record_start_date": {"start_date": start.isoformat()},
        "record_subjects": {"subjects": ["math"]},
        "record_levels": {"levels": ["secondary", "upper_secondary"]},
        "record_availability": {"availability": ["workdays_afternoon", "saturday_morning"]},
        "record_teaching_format": {"teaching_format": "online"},
        "record_work_authorization": {"authorized": authorized},
        "record_experience": {"summary": "two years tutoring"},
    }


async def record_all(deps: ToolDeps, arguments: dict[str, dict[str, Any]]) -> Call:
    """Record every fact; returns the call, whose last result carries the verdict."""
    call = Call(deps)
    for tool, args in arguments.items():
        await call.run(tool, **args)
    return call


async def test_record_start_date_rejects_a_date_in_the_past(deps: ToolDeps, monkeypatch):
    """Eval f/es: "10 de enero" said in November was saved as last January and qualified."""
    monkeypatch.setattr(tools, "_today", lambda deps: date(2026, 11, 11))
    call = await record(deps, "record_start_date", start_date="2026-01-10")
    assert call.result["error"] == "start_date_in_past"
    assert (await deps.store.get_facts(deps.screening_id)).start_date is None


@pytest.mark.parametrize("bad", ["yes", 1])
async def test_record_work_authorization_needs_a_real_boolean(deps: ToolDeps, bad: Any):
    """A truthy string or number must not count as authorized."""
    call = await record(deps, "record_work_authorization", authorized=bad)
    assert "error" in call.result
    assert (await deps.store.get_facts(deps.screening_id)).work_authorized is None


async def test_verdict_reads_confirmed_facts_not_declared_subjects(deps: ToolDeps):
    """The candidate declared math, physics and CS, which the opening needs. Confirming only
    chemistry on the call means no needed subject, whatever was declared."""
    arguments = good_arguments()
    arguments["record_subjects"] = {"subjects": ["chemistry"]}
    call = await record_all(deps, arguments)
    assert call.result["qualified"] is False


async def test_no_verdict_until_the_levels_are_saved(deps: ToolDeps):
    """Subjects and levels are saved by separate tools; every other fact on file, the subjects
    alone give no verdict and name only the levels as left to ask."""
    arguments = good_arguments()
    levels = arguments.pop("record_levels")
    call = await record_all(deps, arguments)
    assert call.result["still_to_ask"] == ["levels"]
    assert "qualified" not in call.result
    await call.run("record_levels", **levels)
    assert call.result["still_to_ask"] == []
    assert call.result["qualified"] is True


async def test_scheduling_is_blocked_unless_qualified(deps: ToolDeps):
    slot = await deps.store.create_slot(
        OnboardingSlot(starts_at=datetime.now(UTC) + timedelta(days=2), mode=SlotMode.ONLINE)
    )
    call = await record(deps, "schedule_onboarding", slot_id=slot.id)
    assert call.result["error"] == "missing_facts"  # not even complete yet

    call = await record_all(deps, good_arguments(authorized=False))
    await call.run("list_onboarding_slots")
    assert call.result["error"] == "not_qualified"
    await call.run("schedule_onboarding", slot_id=slot.id)
    assert call.result["error"] == "not_qualified"
    loaded = await deps.store.get_slot(slot.id)
    assert loaded is not None and loaded.booked == 0
