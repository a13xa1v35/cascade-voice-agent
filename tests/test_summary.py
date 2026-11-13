"""The post-call summary never breaks finalize: a failing model falls back to a summary built
from the recorded facts, and finalize stores the subjects confirmed on the call. Fake
Anthropic client, no network."""

import asyncio
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from hr_screener.config import Settings
from hr_screener.models import (
    Availability,
    CallSummary,
    Candidate,
    Channel,
    Level,
    Opening,
    Outcome,
    Role,
    Screening,
    ScreeningFacts,
    ScreeningStatus,
    Sentiment,
    Subject,
    SummaryDraft,
    TeachingFormat,
)
from hr_screener.observability.observers import CallObservers
from hr_screener.pipeline.bot import _finalize
from hr_screener.screening.summary import summarize_call

OPENING = Opening(
    id="o1", role=Role.TUTOR, location="Madrid", subjects=[Subject.MATH, Subject.PHYSICS]
)
CANDIDATE = Candidate(
    id="c1",
    name="Jo Doe",
    phone="+1555",
    location="Madrid",
    opening_id="o1",
    subjects=[Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE],
)
SCREENING = Screening(
    id="s1", candidate_id="c1", channel=Channel.WEBRTC, outcome=Outcome.NOT_INTERESTED
)
# What was confirmed on the call; start date, authorization and experience are still missing.
FACTS = ScreeningFacts(
    subjects=[Subject.MATH, Subject.PHYSICS],
    levels=[Level.SECONDARY],
    availability=[Availability.WORKDAYS_AFTERNOON],
    teaching_format=TeachingFormat.ONLINE,
)
TRANSCRIPT = [
    {"role": "assistant", "text": "Hi, this is Sofia."},
    {"role": "user", "text": "Hello, do you pay for travel time?"},
]
DRAFT = SummaryDraft(
    key_points=["Teaches math"],
    candidate_questions=["Travel pay?"],
    next_step="Call back",
    sentiment=Sentiment.NEUTRAL,
    frustration_signals=[],
)


class FakeClient:
    """Stands in for anthropic.AsyncAnthropic: records calls, returns or raises."""

    def __init__(self, result: Any = None, error: Exception | None = None, delay: float = 0):
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(parse=self._parse)
        self.beta = SimpleNamespace(messages=self.messages)  # same recorder
        self._result, self._error, self._delay = result, error, delay

    async def _parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result


def ok(parsed: Any = DRAFT, stop: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop)


async def run(settings: Settings, client: Any, transcript=TRANSCRIPT) -> CallSummary:
    return await summarize_call(settings, CANDIDATE, OPENING, SCREENING, FACTS, transcript, client)


def api_error() -> anthropic.APIError:
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "http://x"))


def validation_error() -> Exception:
    try:
        SummaryDraft.model_validate({})
    except Exception as exc:
        return exc
    raise AssertionError


@pytest.mark.parametrize(
    "make_client",
    [
        lambda: FakeClient(error=api_error()),
        lambda: FakeClient(ok(stop="refusal")),
        lambda: FakeClient(ok(stop="max_tokens")),
        lambda: FakeClient(ok(parsed=None)),
        lambda: FakeClient(error=validation_error()),
    ],
    ids=["api_error", "refusal", "max_tokens", "no_parsed_output", "validation"],
)
async def test_failures_fall_back(settings, make_client):
    summary = await run(settings, make_client())
    assert summary.source == "fallback"
    assert summary.key_points  # built from the recorded facts
    assert summary.outcome is Outcome.NOT_INTERESTED


async def seeded(store):
    await store.create_opening(OPENING)
    await store.create_candidate(CANDIDATE)
    await store.create_screening(
        Screening(
            id="s1",
            candidate_id="c1",
            channel=Channel.WEBRTC,
            status=ScreeningStatus.COMPLETED,
            outcome=Outcome.NOT_INTERESTED,
        )
    )
    await store.set_subjects("s1", FACTS.subjects)
    await store.set_levels("s1", FACTS.levels)
    assert FACTS.teaching_format is not None
    await store.set_availability("s1", FACTS.availability)
    await store.set_teaching_format("s1", FACTS.teaching_format)
    await store.save_transcript("s1", TRANSCRIPT)


def observers(store) -> CallObservers:
    return CallObservers("s1", debug=False, redis=store.redis)


async def test_finalize_replaces_declared_subjects_with_the_confirmed_ones(store, settings):
    """The candidate declared math, physics and CS; the call confirmed math and chemistry."""
    await seeded(store)
    await store.set_subjects("s1", [Subject.MATH, Subject.CHEMISTRY])
    await store.set_levels("s1", [Level.PRIMARY])

    async def summarizer(*args: Any) -> CallSummary:
        return CallSummary(language="en", source="llm")

    await _finalize("s1", store, settings, None, observers(store), None, summarizer)
    candidate = await store.get_candidate("c1")
    assert candidate is not None
    assert candidate.subjects == [Subject.MATH, Subject.CHEMISTRY]
    # the screening keeps what was said on the call
    assert (await store.get_facts("s1")).subjects == [Subject.MATH, Subject.CHEMISTRY]


async def test_finalize_survives_a_raising_summarizer(store, settings):
    await seeded(store)

    async def boom(*args: Any) -> CallSummary:
        raise RuntimeError("boom")

    await _finalize("s1", store, settings, None, observers(store), None, boom)
    assert (await store.get_call_metrics("s1")) is not None  # earlier steps unaffected
    summary = await store.get_summary("s1")
    assert summary is not None and summary.source == "fallback"
