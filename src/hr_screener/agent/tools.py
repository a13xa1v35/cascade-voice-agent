"""LLM tools.

`TOOL_SPECS` is the canonical contract (tool and parameter names, JSON types, required).
Everything the model reads in natural language (tool and parameter names, descriptions, the
`hint` / `next_step` texts in results) is English for every call and lives in
prompt_text.py; `build_tools` returns the schema plus one handler per registered tool name.
A handler maps the argument names the model used back to the canonical ones, so the
implementations below only ever see canonical names. Machine keys in results (`error`,
`qualified`, `booked`, ...) are never translated: metrics read them. Only the values the
candidate hears (slot `when` and `location`, `start_date_spoken`) follow the call language
(`Settings.language`), through hr_screener.i18n.

Design notes
- One `record_*` tool per answer (start date, subjects, levels, availability, teaching
  format, work authorization, experience). The subjects and schedule questions have two tools
  each, saved the moment each half is answered; the question counts as answered once both
  halves are on file, and until then `still_to_ask` names only the missing half (`subjects`
  or `levels`, `availability` or `teaching_format`).
  Every parameter is required and typed, with the enum
  values in the JSON schema, so a call either carries the real boolean / date / enum keys the
  deterministic rule reads or is rejected with a structured error.
- Every `record_*` result carries `recorded` and `still_to_ask`. The call that completes
  the facts also carries the verdict (`qualified`, `next_step`, `internal_reasons`), so the
  model never has to remember a separate "evaluate" step. Re-recording a fact overwrites it
  and re-evaluates.
- `outcome` is a plain string validated here against the enum in models.py.
- Tools never raise. Bad input comes back as `{"error": ..., "hint": ...}` so the
  model can correct itself and keep the conversation going.
- Per-session state arrives through `params.app_resources` (a `ToolDeps`), not globals.
- Eligibility is enforced here, not in the prompt: scheduling tools refuse to run
  unless the deterministic rule says the candidate qualifies.
- `search_knowledge` is an async Pipecat tool (registered in bot.py with
  `cancel_on_interruption=False`): the conversation goes on while the lookup runs and a late
  result is delivered by Pipecat. The handler owns the per-call `SearchState`: one search at a
  time, and the searches that did not answer the candidate so that `_finalize` can leave them
  to a recruiter. `refer_to_recruiter` saves a question for a recruiter to follow up.
- `end_call` does not close the line itself: with a `HangupController` it arms a cancelable
  hang-up (see hangup.py) so a candidate who keeps talking is not cut off.
- Spoken dates and slot times come from Babel's CLDR data (hr_screener.i18n), never from the process
  locale (global, and may not be installed). Weekday matching accepts every supported
  language.
"""

import asyncio
import time
import unicodedata
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import (
    EndWorkerFrame,
    FunctionCallResultProperties,
    STTUpdateSettingsFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.processors.aggregators import async_tool_messages
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import FunctionCallParams

from hr_screener import i18n
from hr_screener.agent import prompt_text
from hr_screener.agent.prompt_text import RESULTS, ToolText, fmt
from hr_screener.config import Settings
from hr_screener.i18n import Lang
from hr_screener.models import (
    Availability,
    Level,
    OnboardingSlot,
    Outcome,
    QuestionKey,
    ReferredQuestion,
    ScreeningFacts,
    ScreeningStatus,
    SlotMode,
    Subject,
    TeachingFormat,
)
from hr_screener.observability.metrics import KNOWLEDGE_TOOLS
from hr_screener.pipeline.frames import NoFollowUpFrame
from hr_screener.pipeline.hangup import HangupController, HangupMarkerFrame
from hr_screener.pipeline.providers import stt_settings_for, tts_settings_for
from hr_screener.screening.followup import CallMode
from hr_screener.screening.qualification import (
    evaluate,
    missing_questions,
    question_half_missing,
    still_to_ask,
)
from hr_screener.storage.store import BookingResult, ScreeningStore

if TYPE_CHECKING:  # the knowledge package pulls in qdrant and fastembed: type-only here
    from hr_screener.knowledge.store import KnowledgeBase

MAX_SLOT_OPTIONS = 3

Handler = Callable[[FunctionCallParams], Awaitable[None]]
Args = dict[str, Any]  # arguments with canonical parameter names


@dataclass
class SearchState:
    """What the knowledge search tool tracks during one call.

    `in_flight` gates "one search at a time" and `end_call`. `unreferred` lists, in order,
    the searches that did not answer the candidate and that Sofia has not (yet) passed to a
    recruiter: `no_match`, `kb_unavailable`, and a handler cancelled or still running when
    the call ended. `refer_to_recruiter` resolves the most recent one. `end_call` does not
    clear them: if Sofia said goodbye without referring, `bot._finalize` still saves what is
    left as automatic referred questions, so no candidate question is lost. The entries are
    the Spanish search queries the model wrote (the only text this tool sees), not the
    candidate's words.
    """

    in_flight: bool = False
    query: str | None = None  # the running search
    unreferred: list[str] = field(default_factory=list)

    def begin(self, query: str) -> None:
        self.in_flight = True
        self.query = query

    def end(self, *, answered: bool) -> None:
        """The search is over (also when the handler was cancelled: `answered` False)."""
        query, self.query, self.in_flight = self.query, None, False
        if not answered and query is not None and query not in self.unreferred:
            self.unreferred.append(query)

    def resolve_latest(self) -> None:
        if self.unreferred:
            self.unreferred.pop()

    def unresolved(self) -> list[str]:
        """Queries to save as automatic referred questions once the call is over: the
        unreferred ones, plus a search that is still running (its handler may not have been
        cancelled yet)."""
        pending = list(self.unreferred)
        if self.in_flight and self.query is not None and self.query not in pending:
            pending.append(self.query)
        return pending


@dataclass
class CallLanguage:
    """The language the call is being held in right now. It starts as `Settings.language` and
    `switch_language` changes it; everything that happens during or after the call and speaks to
    the candidate or records the language reads it. Created once per call and shared (the tools,
    the holding line, the LLM recovery apology, finalize)."""

    current: Lang


@dataclass
class ToolDeps:
    """Per-session resources, passed as `PipelineWorker(app_resources=...)`."""

    store: ScreeningStore
    screening_id: str
    settings: Settings
    # Cancelable hang-up. None (standalone use, tests): end_call pushes EndWorkerFrame.
    hangup: HangupController | None = None
    # A closed-mode call (booked / rejected candidate) may only end with already_screened
    # or wrong_person; build_tools offers it end_call alone.
    mode: CallMode = CallMode.FRESH
    # The knowledge base behind search_knowledge. None (standalone use, tests): the tool is
    # not offered (see build_tools).
    knowledge: "KnowledgeBase | None" = None
    search: SearchState = field(default_factory=SearchState)
    # Appends an event to the call timeline (CallRecorder.record). None: nothing is recorded.
    record: Callable[..., None] | None = None
    # A follow-up that starts with every fact saved must confirm the start date before any
    # slot is offered (README, lesson 18): the slot tools refuse until record_start_date ran
    # in this call. A correction the model never records cannot otherwise stop a booking.
    confirm_start_date: bool = False
    start_date_confirmed: bool = False
    # The call language, switchable by the candidate. None: starts as `settings.language`.
    language: CallLanguage | None = None
    # A voice call has STT and TTS services to re-point on a switch; a text call has none.
    voice: bool = False

    def __post_init__(self) -> None:
        if self.language is None:
            self.language = CallLanguage(self.settings.language)

    @property
    def lang(self) -> Lang:
        assert self.language is not None
        return self.language.current


@dataclass(frozen=True)
class ParamSpec:
    type: str  # JSON schema type: string | boolean | array
    required: bool = False
    items: str | None = None  # element type, for arrays
    enum: tuple[str, ...] | None = None  # allowed values (of the elements, for arrays)


@dataclass(frozen=True)
class ToolSpec:
    params: dict[str, ParamSpec]  # canonical parameter name -> spec


def _values(enum: type[StrEnum]) -> tuple[str, ...]:
    return tuple(member.value for member in enum)


# Canonical contract, in the order the tools are offered. Optional parameters are nullable.
TOOL_SPECS: dict[str, ToolSpec] = {
    "switch_language": ToolSpec({"language": ParamSpec("string", required=True, enum=i18n.LANGS)}),
    "record_start_date": ToolSpec({"start_date": ParamSpec("string", required=True)}),
    "record_subjects": ToolSpec(
        {
            "subjects": ParamSpec("array", required=True, items="string", enum=_values(Subject)),
        }
    ),
    "record_levels": ToolSpec(
        {"levels": ParamSpec("array", required=True, items="string", enum=_values(Level))}
    ),
    "record_availability": ToolSpec(
        {
            "availability": ParamSpec(
                "array", required=True, items="string", enum=_values(Availability)
            ),
        }
    ),
    "record_teaching_format": ToolSpec(
        {"teaching_format": ParamSpec("string", required=True, enum=_values(TeachingFormat))}
    ),
    "record_work_authorization": ToolSpec({"authorized": ParamSpec("boolean", required=True)}),
    "record_experience": ToolSpec({"summary": ParamSpec("string", required=True)}),
    "list_onboarding_slots": ToolSpec({"preferred_day": ParamSpec("string")}),
    "schedule_onboarding": ToolSpec({"slot_id": ParamSpec("string", required=True)}),
    "search_knowledge": ToolSpec({"query": ParamSpec("string", required=True)}),
    "refer_to_recruiter": ToolSpec({"question": ParamSpec("string", required=True)}),
    "end_call": ToolSpec(
        {"outcome": ParamSpec("string", required=True), "notes": ParamSpec("string")}
    ),
}


def _fold(text: str) -> str:
    """Lowercase and strip accents, so 'MIÉRCOLES' == 'miercoles'."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Answers that are only a placeholder, compared after _fold and with punctuation stripped.
_PLACEHOLDER_EXACT = frozenset(
    {"", "n/a", "na", "tbd", "tba", "pending", "pendiente", "unknown", "desconocido"}
    | {"placeholder", "none yet"}
)
# Phrases that mark an answer as a placeholder wherever they appear (folded text).
_PLACEHOLDER_PHRASES = (
    "not yet asked", "not asked", "not been asked", "yet to be asked", "to be asked",
    "not answered yet", "not yet answered", "placeholder", "no preguntado", "sin preguntar",
    "todavia no preguntado", "aun no preguntado", "pendiente de preguntar",
)  # fmt: skip


def is_placeholder_answer(answer: str) -> bool:
    """True if `answer` is a placeholder rather than something the candidate said.

    Checked on the accent-folded, lowercased text: empty or a bare marker such as "n/a",
    "TBD", "-" or "?", or containing a phrase like "not yet asked". Genuine short answers
    ("No", "No experience", "none", "no tengo experiencia") are not placeholders.
    """
    folded = _fold(answer)
    bare = folded.strip(" \t\r\n.,;:!¡¿?-\u2013\u2014_*\"'()[]")
    if bare in _PLACEHOLDER_EXACT:
        return True
    return any(phrase in folded for phrase in _PLACEHOLDER_PHRASES)


def _today(deps: ToolDeps) -> date:
    return datetime.now(ZoneInfo(deps.settings.timezone)).date()


async def _verdict(
    deps: ToolDeps, facts: ScreeningFacts
) -> tuple[bool, list[str]] | dict[str, Any]:
    """The rule's (qualified, reasons) for complete facts, or a structured error for the
    model if the screening has no opening."""
    opening = await deps.store.opening_for_screening(deps.screening_id)
    if opening is None:
        return {"error": "opening_not_found"}
    return evaluate(facts, opening, _today(deps))


async def _qualification_error(deps: ToolDeps) -> dict[str, Any] | None:
    """None if the candidate qualifies, otherwise a structured error for the model."""
    if deps.confirm_start_date and not deps.start_date_confirmed:
        return {
            "error": "start_date_unconfirmed",
            "hint": fmt(RESULTS["hint_start_date_unconfirmed"]),
        }
    facts = await deps.store.get_facts(deps.screening_id)
    if missing := missing_questions(facts):
        return {
            "error": "missing_facts",
            "missing": [q.value for q in missing],
            "hint": fmt(RESULTS["hint_missing_facts"]),
        }
    verdict = await _verdict(deps, facts)
    if isinstance(verdict, dict):
        return verdict
    if not verdict[0]:
        return {"error": "not_qualified", "hint": fmt(RESULTS["hint_not_qualified"])}
    return None


def slot_payload(slot: OnboardingSlot, tz: ZoneInfo, lang: Lang) -> dict[str, str]:
    return {
        "slot_id": slot.id,
        "when": i18n.format_slot_time(slot.starts_at, tz, lang),
        "location": i18n.render_location(slot, lang),
    }


def _parse_enums[E: StrEnum](param: str, raw: Any, enum: type[E]) -> list[E] | dict[str, Any]:
    """Distinct enum members for a list argument, or a structured error for the model."""
    valid = list(_values(enum))
    if not isinstance(raw, list) or not raw:
        return {"error": f"{param} must not be empty", "valid": valid}
    invalid = [str(x) for x in raw if x not in valid]
    if invalid:
        return {"error": f"invalid_{param}", "invalid": invalid, "valid": valid}
    return [enum(x) for x in dict.fromkeys(raw)]


async def _recorded(
    params: FunctionCallParams,
    key: QuestionKey,
    extra: dict[str, Any] | None = None,
) -> None:
    """Result of a record_* tool: what is still to ask, and once nothing is, the verdict."""
    deps: ToolDeps = params.app_resources
    facts = await deps.store.get_facts(deps.screening_id)
    still = missing_questions(facts)
    result: dict[str, Any] = {
        "recorded": key.value,
        "still_to_ask": still_to_ask(facts),
        **(extra or {}),
    }
    if half := question_half_missing(facts, key):
        # Subjects and schedule have two halves, each saved on its own: say which is left.
        result["hint"] = fmt(RESULTS[f"hint_{key.value}_missing_{half}"])
    if not still:
        verdict = await _verdict(deps, facts)
        if isinstance(verdict, dict):
            result |= verdict
        else:
            qualified, reasons = verdict
            logger.info(f"qualification qualified={qualified} reasons={reasons}")
            step = "next_step_qualified" if qualified else "next_step_not_qualified"
            # `reasons` is for internal use only; the prompt forbids reading it to the candidate.
            result |= {
                "qualified": qualified,
                "next_step": fmt(RESULTS[step]),
                "internal_reasons": reasons,
            }
    if _already_asked_next(params, result):
        # No follow-up reply: Sofia already asked the next question before this save, and the
        # result tells her nothing new; a forced reply would ask it again (README, lesson 17).
        logger.info("record result without a follow-up reply: the next question was asked")
        await params.result_callback(result, properties=FunctionCallResultProperties(run_llm=False))
        await params.llm.push_frame(NoFollowUpFrame())
        return
    await params.result_callback(result)


# A record_* result with only these keys tells the model nothing it must act on.
_PLAIN_RESULT_KEYS = frozenset({"recorded", "still_to_ask"})


def _already_asked_next(params: FunctionCallParams, result: Mapping[str, Any]) -> bool:
    """True when the follow-up reply to a save is redundant: the save was the only tool call of
    the response, its result is plain (no verdict, hint, error or spoken value to read back),
    and the text the model wrote with it ends with a question. The text comes from Sofia's LLM
    service (`llm.services.ResponseTracker`); another service (tests, the bench) never skips."""
    if set(result) - _PLAIN_RESULT_KEYS or not result.get("still_to_ask"):
        return False
    llm = params.llm
    if getattr(llm, "response_tool_calls", 0) != 1:
        return False
    text = getattr(llm, "response_text", "")
    return isinstance(text, str) and text.rstrip().endswith("?")


async def _record_start_date(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    start_date = args["start_date"]
    logger.info(f"tool record_start_date start_date={start_date!r}")
    try:
        parsed = date.fromisoformat(start_date)
    except (TypeError, ValueError):
        await params.result_callback({"error": "start_date must be YYYY-MM-DD", "got": start_date})
        return
    today = _today(deps)
    if parsed < today:
        # A date the model resolved to the wrong year (a month beyond the prompt's calendar,
        # e.g. "10 January" in November) must not be saved: it would also pass the rule.
        await params.result_callback(
            {
                "error": "start_date_in_past",
                "got": start_date,
                "today": today.isoformat(),
                "hint": fmt(RESULTS["hint_start_date_in_past"]),
            }
        )
        return
    await deps.store.set_start_date(deps.screening_id, parsed)
    deps.start_date_confirmed = True  # said in this call: confirmed, or corrected
    # Read back from here: the model must not do date arithmetic.
    spoken = {"start_date_spoken": i18n.format_date(parsed, deps.lang)}
    await _recorded(params, QuestionKey.AVAILABILITY_START, spoken)


async def _record_subjects(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    logger.info(f"tool record_subjects subjects={args['subjects']!r}")
    subjects = _parse_enums("subjects", args["subjects"], Subject)
    if isinstance(subjects, dict):
        await params.result_callback(subjects)
        return
    await deps.store.set_subjects(deps.screening_id, subjects)
    await _recorded(params, QuestionKey.SUBJECTS)


async def _record_levels(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    logger.info(f"tool record_levels levels={args['levels']!r}")
    levels = _parse_enums("levels", args["levels"], Level)
    if isinstance(levels, dict):
        await params.result_callback(levels)
        return
    await deps.store.set_levels(deps.screening_id, levels)
    await _recorded(params, QuestionKey.SUBJECTS)


async def _record_availability(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    logger.info(f"tool record_availability availability={args['availability']!r}")
    availability = _parse_enums("availability", args["availability"], Availability)
    if isinstance(availability, dict):
        await params.result_callback(availability)
        return
    await deps.store.set_availability(deps.screening_id, availability)
    await _recorded(params, QuestionKey.SCHEDULE)


async def _record_teaching_format(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    logger.info(f"tool record_teaching_format teaching_format={args['teaching_format']!r}")
    try:
        teaching_format = TeachingFormat(args["teaching_format"])
    except ValueError:
        await params.result_callback(
            {
                "error": f"invalid teaching_format {args['teaching_format']!r}",
                "valid": list(_values(TeachingFormat)),
            }
        )
        return
    await deps.store.set_teaching_format(deps.screening_id, teaching_format)
    await _recorded(params, QuestionKey.SCHEDULE)


async def _record_work_authorization(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    authorized = args["authorized"]
    logger.info(f"tool record_work_authorization authorized={authorized!r}")
    if not isinstance(authorized, bool):
        await params.result_callback({"error": "authorized must be true or false"})
        return
    await deps.store.set_work_authorized(deps.screening_id, authorized)
    await _recorded(params, QuestionKey.WORK_AUTHORIZATION)


async def _record_experience(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    summary = args["summary"]
    logger.info(f"tool record_experience summary={summary!r}")
    if not isinstance(summary, str) or is_placeholder_answer(summary):
        await params.result_callback(
            {"error": "placeholder_answer", "hint": fmt(RESULTS["hint_placeholder"])}
        )
        return
    await deps.store.set_experience(deps.screening_id, summary.strip())
    await _recorded(params, QuestionKey.RELEVANT_EXPERIENCE)


async def _list_onboarding_slots(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    preferred_day: str | None = args.get("preferred_day")
    logger.info(f"tool list_onboarding_slots preferred_day={preferred_day!r}")

    if error := await _qualification_error(deps):
        await params.result_callback(error)
        return

    tz = ZoneInfo(deps.settings.timezone)
    slots = await deps.store.list_open_slots(datetime.now(tz), limit=50)

    matched_preference = True
    if preferred_day:
        wanted = _fold(preferred_day)
        wanted_weekday = i18n.weekday_index(preferred_day)
        filtered = [
            s
            for s in slots
            if wanted == _iso_day(s, tz) or s.starts_at.astimezone(tz).weekday() == wanted_weekday
        ]
        if filtered:
            slots = filtered
        else:
            matched_preference = False  # fall back to the soonest slots overall

    # Ordering preference, not a filter: slots in the candidate's mode first, soonest first
    # within each group (the sort is stable).
    facts = await deps.store.get_facts(deps.screening_id)
    preferred_mode = _PREFERRED_MODE.get(facts.teaching_format)
    if preferred_mode is not None:
        slots = sorted(slots, key=lambda s: s.mode is not preferred_mode)

    lang = deps.lang
    options = [slot_payload(s, tz, lang) for s in slots[:MAX_SLOT_OPTIONS]]
    if not options:
        await params.result_callback({"error": "no_open_slots"})
        return
    await params.result_callback({"slots": options, "matched_preferred_day": matched_preference})


_PREFERRED_MODE: dict[TeachingFormat | None, SlotMode] = {
    TeachingFormat.ONLINE: SlotMode.ONLINE,
    TeachingFormat.IN_PERSON: SlotMode.IN_PERSON,
}


def _iso_day(slot: OnboardingSlot, tz: ZoneInfo) -> str:
    return slot.starts_at.astimezone(tz).date().isoformat()


async def _schedule_onboarding(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    slot_id: str = args["slot_id"]
    logger.info(f"tool schedule_onboarding slot_id={slot_id!r}")

    if error := await _qualification_error(deps):
        await params.result_callback(error)
        return

    result = await deps.store.book_slot(deps.screening_id, slot_id)
    logger.info(f"booking result={result.value}")

    if result in (BookingResult.BOOKED, BookingResult.ALREADY_BOOKED):
        slot = await deps.store.get_slot(slot_id)
        assert slot is not None  # booking succeeded, so the slot exists
        tz = ZoneInfo(deps.settings.timezone)
        await params.result_callback({"booked": True, **slot_payload(slot, tz, deps.lang)})
        return
    error_key = {
        BookingResult.FULL: ("slot_full", "hint_slot_full"),
        BookingResult.HAS_OTHER_SLOT: ("already_booked", "hint_already_booked"),
    }.get(result, ("unknown_slot", "hint_unknown_slot"))
    await params.result_callback({"error": error_key[0], "hint": fmt(RESULTS[error_key[1]])})


def _record(deps: ToolDeps, event: str, **data: Any) -> None:
    if deps.record is not None:
        deps.record(event, **data)


def _delivered_late(params: FunctionCallParams) -> bool:
    """True when the result will be delivered as a deferred message: a user or developer
    message already follows this call's placeholder in the context (the same rule Pipecat's
    aggregator applies when it settles the call, see `_is_deferred`). Read just before the
    result is handed over, so a turn that starts in between is missed: it is a measurement,
    not a decision."""
    messages = getattr(getattr(params, "context", None), "messages", None) or []
    after_placeholder = False
    for message in messages:
        if not isinstance(message, dict):
            continue
        if not after_placeholder:
            after_placeholder = (
                message.get("role") == "tool" and message.get("tool_call_id") == params.tool_call_id
            )
            continue
        if message.get("role") in ("tool", "assistant"):
            continue
        payload = async_tool_messages.parse_message(message)
        if payload is not None and payload.tool_call_id != params.tool_call_id:
            continue
        return True
    return False


def _search_payload(found: Any) -> dict[str, Any]:
    """The tool result for a search that ran: the chunks, or `no_match`."""
    if found.no_match or not found.hits:
        return {"no_match": True, "hint": fmt(RESULTS["hint_no_match"])}
    return {
        "results": [
            {
                "id": hit.id,
                "kind": hit.kind,
                "title": hit.title,
                "text": hit.text,
                # policy chunks have neither a date nor a source
                **({"as_of": hit.as_of} if hit.as_of else {}),
                **({"source": hit.source} if hit.source else {}),
            }
            for hit in found.hits
        ],
        "kb_version": found.kb_version,
    }


async def _search_knowledge(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    query = args["query"]
    logger.info(f"tool search_knowledge query={query!r}")
    if not isinstance(query, str) or not query.strip():
        await params.result_callback(
            {"error": "empty_query", "hint": fmt(RESULTS["hint_empty_query"])}
        )
        return
    query = query.strip()
    state = deps.search
    if state.in_flight:
        await params.result_callback(
            {"error": "already_searching", "hint": fmt(RESULTS["hint_already_searching"])}
        )
        return

    state.begin(query)
    answered = False  # stays False if the handler is cancelled before the result is handed over
    try:
        started = time.monotonic()
        found = error = None
        try:
            if deps.knowledge is None:
                raise RuntimeError("no knowledge base configured")
            async with asyncio.timeout(deps.settings.kb_timeout_secs):
                found = await deps.knowledge.search(query, deps.settings.kb_top_k)
        except Exception as e:  # tools never raise: every failure is "kb_unavailable"
            error = "timeout" if isinstance(e, TimeoutError) else type(e).__name__
            logger.warning(f"search_knowledge failed ({error}): {e!r}")
        total_ms = (time.monotonic() - started) * 1000
        _record(
            deps,
            "kb_search",
            query=query,
            language=deps.lang,
            chunk_ids=[h.id for h in found.hits] if found else [],
            best_dense_score=found.best_dense_score if found else None,
            no_match=found.no_match if found else None,
            error=error,
            embed_ms=round(found.embed_ms, 1) if found else None,
            search_ms=round(found.search_ms, 1) if found else None,
            total_ms=round(total_ms, 1),
            cache_hit=found.query_cache_hit if found else None,
            kb_version=found.kb_version if found else None,
        )
        if found is None:
            payload: dict[str, Any] = {
                "error": "kb_unavailable",
                "hint": fmt(RESULTS["hint_kb_unavailable"]),
            }
        else:
            payload = _search_payload(found)
        _record(
            deps,
            "kb_result_delivered",
            mode="deferred" if _delivered_late(params) else "inline",
            delay_ms=round((time.monotonic() - started) * 1000, 1),
            outcome="kb_unavailable"
            if found is None
            else ("no_match" if "no_match" in payload else "found"),
        )
        # A search without an answer stays open until refer_to_recruiter; _finalize saves
        # what is still open when the call ends.
        answered = found is not None and "no_match" not in payload
        await params.result_callback(payload)
    finally:
        state.end(answered=answered)


async def _refer_to_recruiter(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    question = args["question"]
    logger.info(f"tool refer_to_recruiter question={question!r}")
    if not isinstance(question, str) or not question.strip():
        await params.result_callback({"error": "empty_question"})
        return
    referred = await deps.store.create_referred_question(
        ReferredQuestion(
            screening_id=deps.screening_id,
            question=question.strip(),
            automatic=False,
            language=deps.lang,
        )
    )
    deps.search.resolve_latest()
    _record(
        deps,
        "question_referred",
        question=referred.question,
        automatic=False,
    )
    await params.result_callback({"recorded": True})


async def _switch_language(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    new = args["language"]
    logger.info(f"tool switch_language language={new!r}")
    if new not in i18n.LANGS:
        await params.result_callback({"error": "invalid_language", "valid": list(i18n.LANGS)})
        return
    old = deps.lang
    if new == old:
        await params.result_callback({"already": old})
        return
    assert deps.language is not None
    deps.language.current = new
    _record(deps, "language_switched", **{"from": old, "to": new})
    if deps.voice:
        # Both frames are queued before the result is handed over, so they land ahead of the
        # text spoken after it. TTS is downstream of the LLM, STT upstream.
        await params.llm.push_frame(
            TTSUpdateSettingsFrame(delta=tts_settings_for(deps.settings, new, delta=True))
        )
        await params.llm.push_frame(
            STTUpdateSettingsFrame(delta=stt_settings_for(deps.settings, new)),
            FrameDirection.UPSTREAM,
        )
    # Lazy: prompts imports this module (slot_payload).
    from hr_screener.agent.prompts import language_rule

    knowledge = deps.knowledge is not None and knowledge_offered(deps.mode)
    await params.result_callback(
        {"speak": new, "language_rule": language_rule(deps.settings, new, knowledge=knowledge)}
    )


async def _end_call(params: FunctionCallParams, args: Args) -> None:
    deps: ToolDeps = params.app_resources
    outcome: str = args["outcome"]
    notes: str | None = args.get("notes")
    logger.info(f"tool end_call outcome={outcome!r} notes={notes!r}")

    if deps.mode.is_closed:
        allowed = [Outcome.ALREADY_SCREENED.value, Outcome.WRONG_PERSON.value]
    else:  # already_screened belongs to closed mode; no_answer is set by the system
        hidden = (Outcome.NO_ANSWER, Outcome.ALREADY_SCREENED)
        allowed = [o.value for o in Outcome if o not in hidden]
    if outcome not in allowed:
        await params.result_callback({"error": f"unknown outcome {outcome!r}", "valid": allowed})
        return

    if deps.search.in_flight:
        # The answer is still on its way: give it before saying goodbye.
        await params.result_callback(
            {"error": "search_pending", "hint": fmt(RESULTS["hint_search_pending"])}
        )
        return

    screening = await deps.store.get_screening(deps.screening_id)
    if outcome == Outcome.SCHEDULED and (screening is None or screening.slot_id is None):
        await params.result_callback(
            {"error": "nothing_booked", "hint": fmt(RESULTS["hint_nothing_booked"])}
        )
        return

    await deps.store.finish_screening(
        deps.screening_id, ScreeningStatus.COMPLETED, Outcome(outcome), notes
    )
    # run_llm=False: the goodbye was already spoken, so don't start another LLM turn
    # that would race the shutdown (or talk over the hang-up).
    await params.result_callback(
        {"status": "hanging_up", "hint": fmt(RESULTS["hint_hanging_up"])},
        properties=FunctionCallResultProperties(run_llm=False),
    )
    if deps.hangup is not None:
        # Arm first, then the marker: it travels behind the queued goodbye audio, and the
        # controller closes the line only after it has left the output transport + grace.
        deps.hangup.arm(outcome)
        await params.llm.push_frame(HangupMarkerFrame())
    else:
        # Pushed downstream so queued speech (the goodbye) finishes before the pipeline stops.
        await params.llm.push_frame(EndWorkerFrame())


_IMPLS: dict[str, Callable[[FunctionCallParams, Args], Awaitable[None]]] = {
    "switch_language": _switch_language,
    "record_start_date": _record_start_date,
    "record_subjects": _record_subjects,
    "record_levels": _record_levels,
    "record_availability": _record_availability,
    "record_teaching_format": _record_teaching_format,
    "record_work_authorization": _record_work_authorization,
    "record_experience": _record_experience,
    "list_onboarding_slots": _list_onboarding_slots,
    "schedule_onboarding": _schedule_onboarding,
    "search_knowledge": _search_knowledge,
    "refer_to_recruiter": _refer_to_recruiter,
    "end_call": _end_call,
}


def _param_schema(spec: ParamSpec, description: str) -> dict[str, Any]:
    base: dict[str, Any] = {"type": spec.type}
    if spec.items:
        items: dict[str, Any] = {"type": spec.items}
        if spec.enum:
            items["enum"] = list(spec.enum)
        base["items"] = items
    elif spec.enum:
        base["enum"] = list(spec.enum)
    if spec.required:
        return {**base, "description": description}
    return {"anyOf": [base, {"type": "null"}], "description": description}


def _make_handler(canonical: str, text: ToolText) -> Handler:
    spec = TOOL_SPECS[canonical]
    to_canonical = {p.name: canon for canon, p in text.params.items()}
    localized = {canon: p.name for canon, p in text.params.items()}
    impl = _IMPLS[canonical]

    async def handler(params: FunctionCallParams) -> None:
        raw = params.arguments if isinstance(params.arguments, dict) else {}
        args = {to_canonical.get(name, name): value for name, value in raw.items()}
        missing = [
            localized[name]
            for name, p in spec.params.items()
            if p.required and args.get(name) is None
        ]
        if missing:
            await params.result_callback({"error": "missing_arguments", "missing": missing})
            return
        await impl(params, args)

    return handler


# The only tools a closed-mode call is offered (it may still switch language), besides the
# knowledge tools when it has them.
CLOSED_TOOLS = ("switch_language", "end_call")


def knowledge_offered(mode: CallMode) -> bool:
    """Whether a call in `mode` may use the knowledge tools (given a knowledge base): every
    mode but closed_rejected, which gets a polite close and nothing else."""
    return mode is not CallMode.CLOSED_REJECTED


def build_tools(
    mode: CallMode = CallMode.FRESH, *, knowledge: bool = False, kb_language: str = "es"
) -> tuple[ToolsSchema, dict[str, Handler]]:
    """The tool schema the model sees and the handlers to register, keyed by tool name.
    Register each with `llm.register_function(name, handler)`. A closed-mode call gets
    `end_call` only, with its narrower description.

    `knowledge` adds `search_knowledge` and `refer_to_recruiter` (when `knowledge_offered` for
    `mode`); `kb_language` is the knowledge base language the query is written in."""
    offered = knowledge and knowledge_offered(mode)
    language_name = prompt_text.PROMPT[f"lang_name_{kb_language}"]
    schemas: list[FunctionSchema] = []
    handlers: dict[str, Handler] = {}
    for canonical, spec in TOOL_SPECS.items():
        if canonical in KNOWLEDGE_TOOLS:
            if not offered:
                continue
        elif mode.is_closed and canonical not in CLOSED_TOOLS:
            continue
        closed_end_call = mode.is_closed and canonical == "end_call"
        text = prompt_text.END_CALL_CLOSED if closed_end_call else prompt_text.TOOLS[canonical]
        schemas.append(
            FunctionSchema(
                name=text.name,
                description=fmt(text.description, kb_language=language_name),
                properties={
                    text.params[p].name: _param_schema(
                        s, fmt(text.params[p].description, kb_language=language_name)
                    )
                    for p, s in spec.params.items()
                },
                required=[text.params[p].name for p, s in spec.params.items() if s.required],
            )
        )
        handlers[text.name] = _make_handler(canonical, text)
    return ToolsSchema(standard_tools=list(schemas)), handlers
