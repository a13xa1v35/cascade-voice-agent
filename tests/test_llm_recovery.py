"""Two LLM failures in a row end the call with a spoken apology, and the screening stays
resumable with what was recorded. Runs the real text-channel pipeline with a scripted LLM
that fails on request. No network."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from textcall_helpers import Fail, claimed_screening, new_call

from hr_screener import i18n
from hr_screener.models import Channel, ScreeningStatus
from hr_screener.screening.followup import CallMode, load_call_context, new_screening

S = ScreeningStatus
APOLOGY = i18n.llm_error_apology("en")
# record_start_date rejects a date before the real today (in the settings timezone, UTC)
START = datetime.now(UTC).date() + timedelta(days=30)


def types(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


async def test_two_failures_in_a_row_apologize_end_and_stay_resumable(
    store, text_settings, opening, script_llm
):
    llm = script_llm(
        [
            ("Hello Maria", []),
            ("Noted.", [("record_start_date", {"start_date": START.isoformat()})]),
            ("Which subjects do you teach?", []),
            Fail(),
            Fail(),
        ]
    )
    screening = await claimed_screening(store, opening)
    call = new_call(store, text_settings, screening)
    call.start()
    await call.next_reply(10)
    await call.say("I can start on 16 November", 10)
    assert await call.say("Maths", 10) == APOLOGY
    assert await call.next_reply(10) is None  # then the call ends by itself
    await call.wait_done()
    assert len(llm.runs) == 5  # one retry, no third attempt

    assert await call.end_reason() == "llm_error"
    done = await store.get_screening(screening.id)
    assert (done.status, done.outcome, done.notes) == (S.FAILED, None, "llm_error")
    transcript = await store.get_transcript(screening.id)
    assert APOLOGY not in [t["text"] for t in transcript]  # not a turn of the conversation
    events = await store.get_events(screening.id)
    assert types(events).count("llm.error") == 2 and types(events).count("llm.retry") == 1
    (gave_up,) = [e["data"] for e in events if e["type"] == "llm.gave_up"]
    assert gave_up == {"quota": False, "failures": 2}

    # the next call for the candidate resumes it, with what was recorded
    candidate = await store.get_candidate(screening.candidate_id)
    follow = await new_screening(store, candidate, Channel.TEXT, today=date.today())
    assert (follow.previous_screening_id, follow.attempt) == (screening.id, 2)
    context = await load_call_context(store, follow)
    assert context.mode is CallMode.FOLLOWUP and context.followup is not None
    assert context.followup.facts.start_date == START
