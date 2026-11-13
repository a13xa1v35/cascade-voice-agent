"""A new call for a candidate ends the live one and resumes it, without clobbering an outcome
finalize already wrote; the audio watchdog ends a call whose audio stopped."""

import asyncio
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hr_screener.app.api import create_app
from hr_screener.models import (
    Candidate,
    Channel,
    Outcome,
    Screening,
    ScreeningStatus,
    Subject,
)
from hr_screener.pipeline.bot import _finish_status
from hr_screener.pipeline.watchdog import AudioWatchdog
from hr_screener.screening.calls import LiveCall, LiveCalls, supersede_live_call
from hr_screener.storage.store import ScreeningStore

S = ScreeningStatus

# The API path clears a carried start date before the real today, so keep it ahead.
START = date.today() + timedelta(days=30)


async def seed_live_call(store: ScreeningStore, opening) -> tuple[Candidate, Screening]:
    """Screening A: in progress, with the start date and subjects already recorded."""
    candidate = await store.create_candidate(
        Candidate(
            name="Maria Lopez",
            phone="+34600",
            location="Madrid",
            opening_id=opening.id,
            subjects=[Subject.MATH],
        )
    )
    a = await store.create_screening(
        Screening(candidate_id=candidate.id, channel=Channel.WEBRTC, status=S.IN_PROGRESS)
    )
    await store.set_start_date(a.id, START)
    await store.set_subjects(a.id, [Subject.MATH, Subject.PHYSICS])
    return candidate, a


def register_with_real_finalize(
    app: FastAPI, store: ScreeningStore, settings, screening_id: str
) -> LiveCall:
    """A live call whose stop runs the real status step of finalize, then signals it."""
    live = app.state.live_calls.register(screening_id)

    async def stop() -> None:
        # what _run_call's stop does (end reason superseded), then _finalize's status step
        await _finish_status(screening_id, store, settings)
        live.status_final.set()

    live.bind_stop(stop)
    return live


def assert_resumed(client_result: dict[str, Any], a_id: str, store: ScreeningStore):
    b_id = client_result["session_id"]
    assert client_result["attempt"] == 2
    assert client_result["previous_screening_id"] == a_id
    facts = asyncio.run(store.get_facts(b_id))
    assert facts.start_date == START
    assert facts.subjects == [Subject.MATH, Subject.PHYSICS]


def test_new_call_ends_the_live_one_and_resumes(redis, engine, store, settings, opening):
    candidate, a = asyncio.run(seed_live_call(store, opening))
    app = create_app(redis=redis, settings=settings, engine=engine)
    with TestClient(app) as client:
        live = register_with_real_finalize(app, store, settings, a.id)
        res = client.post("/screenings", json={"candidate_id": candidate.id}).json()
        assert live.end_requested
        old = asyncio.run(store.get_screening(a.id))
        assert old is not None and old.status is S.FAILED and old.outcome is None
        assert_resumed(res, a.id, store)


async def test_a_finalize_that_wins_the_race_is_not_clobbered(store, opening):
    candidate, a = await seed_live_call(store, opening)
    calls = LiveCalls()
    live = calls.register(a.id)

    async def stop() -> None:
        # finalize inferred an outcome right before the supersede got to it
        await store.finish_screening(a.id, S.COMPLETED, Outcome.NOT_QUALIFIED, "inferred")
        live.status_final.set()

    live.bind_stop(stop)
    await supersede_live_call(store, calls, candidate.id, 1.0)
    done = await store.get_screening(a.id)
    assert done is not None
    assert (done.status, done.outcome, done.notes) == (
        S.COMPLETED,
        Outcome.NOT_QUALIFIED,
        "inferred",
    )

    # a call already completed (not in progress) is never touched
    candidate2, a2 = await seed_live_call(store, opening)
    await store.finish_screening(a2.id, S.COMPLETED, Outcome.SCHEDULED, "booked")
    await supersede_live_call(store, calls, candidate2.id, 1.0)
    assert (await store.get_screening(a2.id)).outcome is Outcome.SCHEDULED


# --- audio watchdog ---


async def test_watchdog_fires_after_the_gap():
    lost = asyncio.Event()

    async def on_lost() -> None:
        lost.set()

    wd = AudioWatchdog(0.15, on_lost, poll_secs=0.02)
    wd.start()
    await asyncio.wait_for(lost.wait(), 2)
    await wd.stop()


async def test_watchdog_stays_quiet_while_frames_flow_and_stops_cleanly():
    fired: list[int] = []

    async def on_lost() -> None:
        fired.append(1)

    wd = AudioWatchdog(0.15, on_lost, poll_secs=0.02)
    wd.start()
    for _ in range(15):  # 0.45 s, three times the limit
        wd.note_audio()
        await asyncio.sleep(0.03)
    assert fired == []
    await wd.stop()
    await asyncio.sleep(0.3)  # stopped: never fires afterwards
    assert fired == []
