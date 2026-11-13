"""Post-call summary.

The summary is one direct Anthropic call made AFTER the pipeline is down (the hang-up
cancels the pipeline worker, so it cannot be a pipeline turn). It never raises: any
failure yields a deterministic summary built from the recorded facts instead.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import anthropic
import pydantic
from loguru import logger

from hr_screener import i18n
from hr_screener.agent.prompt_text import PROMPT, fmt
from hr_screener.agent.prompts import fact_values
from hr_screener.citations import verified_quotes
from hr_screener.config import Settings
from hr_screener.models import (
    CallSummary,
    Candidate,
    Opening,
    Outcome,
    Screening,
    ScreeningFacts,
    SummaryDraft,
)
from hr_screener.screening.qualification import evaluate, missing_questions

MAX_TOKENS = 4000  # includes adaptive thinking tokens

# Models that accept the server-side refusal fallback (`fallbacks: "default"`). Haiku has
# none; there a refusal just yields the deterministic fallback summary.
_SERVER_FALLBACK_MODELS = (
    "claude-sonnet-5-5",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-fable-5-1",
)
_SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Signature of summarize_call; _finalize takes it as a parameter so tests can swap it.
Summarizer = Callable[..., Awaitable[CallSummary]]


def _qualified(facts: ScreeningFacts, opening: Opening, settings: Settings) -> bool | None:
    """The deterministic rule's verdict; None while the facts are incomplete."""
    if missing_questions(facts):
        return None
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    return evaluate(facts, opening, today)[0]


def fallback_summary(
    settings: Settings,
    screening: Screening,
    facts: ScreeningFacts,
    opening: Opening,
) -> CallSummary:
    """No LLM: key points are the recorded facts, the next step is generic. Both are for
    the recruiter, so they are worded in the call language."""
    words = i18n.fact_words(settings.language)
    return CallSummary(
        outcome=screening.outcome,
        qualified=_qualified(facts, opening, settings),
        key_points=[
            f"{words.field(key.value)}: {value}" for key, value in fact_values(facts, words).items()
        ],
        next_step=i18n.summary_fallback_next_step(
            settings.language, already_screened=screening.outcome is Outcome.ALREADY_SCREENED
        ),
        language=settings.language,
        source="fallback",
    )


def _user_message(
    candidate: Candidate,
    opening: Opening,
    screening: Screening,
    facts: ScreeningFacts,
    transcript: list[dict[str, str]],
) -> str:
    payload = {
        "candidate": {
            "name": candidate.name,
            "declared_subjects": [s.value for s in candidate.subjects],
        },
        "opening": opening.model_dump(mode="json", exclude={"id", "created_at"}),
        "outcome": screening.outcome.value if screening.outcome else None,
        "attempt": screening.attempt,
        "previous_screening_id": screening.previous_screening_id,
        "facts": facts.model_dump(mode="json", exclude_none=True),
        "transcript": transcript,
    }
    return json.dumps(payload, ensure_ascii=False)


async def parse_structured(client: anthropic.AsyncAnthropic, request: dict[str, Any]) -> Any:
    """One structured-output call (`request` carries `output_format`). Shared with the answer
    job. The caller checks `stop_reason`; API and validation errors propagate. Logs the token
    usage, which is what the post-call calls cost."""
    model = request["model"]
    if model in _SERVER_FALLBACK_MODELS:
        # A policy decline is re-run server-side on a fallback model in the same call.
        response = await client.beta.messages.parse(
            **request, betas=[_SERVER_FALLBACK_BETA], fallbacks="default"
        )
    else:
        response = await client.messages.parse(**request)
    if usage := getattr(response, "usage", None):
        logger.info(
            f"{model} tokens in={getattr(usage, 'input_tokens', '?')} "
            f"out={getattr(usage, 'output_tokens', '?')}"
        )
    return response


async def _ask_llm(
    client: anthropic.AsyncAnthropic,
    settings: Settings,
    candidate: Candidate,
    opening: Opening,
    screening: Screening,
    facts: ScreeningFacts,
    transcript: list[dict[str, str]],
) -> SummaryDraft | None:
    model = settings.effective_summary_model
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        # The instructions are English; the summary is written in the call language.
        "system": fmt(
            PROMPT["summary_instructions"], language=PROMPT[f"lang_name_{settings.language}"]
        ),
        "messages": [
            {
                "role": "user",
                "content": _user_message(candidate, opening, screening, facts, transcript),
            }
        ],
        "output_format": SummaryDraft,
        "output_config": {"effort": "low"},
    }
    response = await parse_structured(client, request)
    if response.stop_reason in ("refusal", "max_tokens"):
        logger.warning(f"[{screening.id}] summary unusable: stop_reason={response.stop_reason}")
        return None
    return response.parsed_output


async def summarize_call(
    settings: Settings,
    candidate: Candidate,
    opening: Opening,
    screening: Screening,
    facts: ScreeningFacts,
    transcript: list[dict[str, str]],
    client: anthropic.AsyncAnthropic | None = None,
) -> CallSummary:
    """Summary in the call language. Falls back (never raises) when disabled, when there is
    no key or transcript, or when the LLM call fails, times out, refuses or returns junk."""
    fallback = fallback_summary(settings, screening, facts, opening)
    if not settings.summary_enabled or not transcript:
        return fallback
    if client is None:
        if not settings.anthropic_api_key:
            return fallback
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        draft = await asyncio.wait_for(
            _ask_llm(client, settings, candidate, opening, screening, facts, transcript),
            timeout=settings.summary_timeout_secs,
        )
    except TimeoutError:
        logger.warning(f"[{screening.id}] summary timed out, using fallback")
        return fallback
    except anthropic.APIError as exc:
        logger.warning(f"[{screening.id}] summary API error, using fallback: {exc}")
        return fallback
    except pydantic.ValidationError as exc:
        logger.warning(f"[{screening.id}] summary did not validate, using fallback: {exc}")
        return fallback
    if draft is None:
        return fallback
    # Quotes must be the candidate's own words; one that is not is dropped (citations.py).
    candidate_turns = [t["text"] for t in transcript if t.get("role") == "user"]
    signals = verified_quotes(draft.frustration_signals, candidate_turns)
    if dropped := len(draft.frustration_signals) - len(signals):
        logger.warning(f"[{screening.id}] summary: dropped {dropped} unverifiable quote(s)")
    return CallSummary(
        outcome=fallback.outcome,
        qualified=fallback.qualified,
        key_points=draft.key_points,
        candidate_questions=draft.candidate_questions,
        next_step=draft.next_step,
        sentiment=draft.sentiment,
        frustration_signals=signals,
        language=settings.language,
        source="llm",
    )
