"""Per-call scorecard, computed after the call from the recorded event timeline.

Pure functions, no I/O: `compute_scorecard(events, screening, facts, thresholds)`.
The events are the dicts written by `observability.CallRecorder`
(`{"t": secs since call start, "wall": ISO UTC, "type": "...", "data": {...}}`).
Every definition is spelled out in docs/metrics.md; the thresholds live in
`MetricsThresholds`.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Any, Literal

from pydantic import BaseModel, Field

from hr_screener.models import Screening, ScreeningFacts
from hr_screener.screening.qualification import missing_questions
from hr_screener.turn_taking.events import summarize_events

Event = dict[str, Any]

RECORD_TOOLS = (
    "record_start_date",
    "record_subjects",
    "record_levels",
    "record_availability",
    "record_teaching_format",
    "record_work_authorization",
    "record_experience",
)
# The knowledge tools (README): allowed anywhere before end_call.
KNOWLEDGE_TOOLS = ("search_knowledge", "refer_to_recruiter")
FAREWELL_WORDS = (
    # EN
    "bye",
    "goodbye",
    "take care",
    "have a great",
    "have a good",
    "see you",
    # ES (accents are folded before matching, so "adios" matches "adiós")
    "adios",
    "hasta luego",
    "hasta pronto",
    "hasta el",  # "hasta el miércoles"
    "nos vemos",
    "que vaya bien",
    "que tengas",
    "un saludo",
    "chao",
)


@dataclass(frozen=True)
class MetricsThresholds:
    # Turn ended, then the user spoke again before bot audio, or within this many
    # seconds after bot audio started: the endpoint was a false one.
    false_endpoint_resume_secs: float = 1.0
    # end_call within this many seconds of the user's last speech_stopped (or while
    # they are speaking) is an unsafe hang-up.
    unsafe_hangup_secs: float = 2.0
    # Endpoint delay (speech_stopped -> turn_ended) at or above this is assumed to be the
    # Smart Turn stop_secs fallback.
    silence_fallback_secs: float = 2.8
    # A frustration judgment at or above this probability counts as "frustrated".
    frustration_probability: float = 0.5


# --- helpers -----------------------------------------------------------------------


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Linear-interpolated percentile (pct in 0..100). None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


class Stats(BaseModel):
    count: int = 0
    p50: float | None = None
    p95: float | None = None
    max: float | None = None

    @classmethod
    def of(cls, values: Sequence[float]) -> "Stats":
        return cls(
            count=len(values),
            p50=_round(percentile(values, 50)),
            p95=_round(percentile(values, 95)),
            max=_round(max(values)) if values else None,
        )


# --- output models -----------------------------------------------------------------

ExchangeKind = Literal["answered", "false_endpoint", "barge_in", "unanswered"]


class ToolCall(BaseModel):
    t: float
    name: str
    tool_call_id: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    status: str = "started"  # started / in_progress / completed / failed / timed_out / cancelled
    error: str | None = None

    @property
    def ran(self) -> bool:
        return self.status in ("in_progress", "completed", "failed", "timed_out")

    @property
    def ok(self) -> bool:
        """Completed and the tool itself did not return a structured error."""
        if self.status != "completed":
            return False
        return not (isinstance(self.result, dict) and "error" in self.result)


class Exchange(BaseModel):
    index: int
    kind: ExchangeKind
    turn_ended_t: float
    user_text: str = ""
    bot_text: str | None = None
    bot_started_t: float | None = None
    reply_latency_secs: float | None = None
    endpoint_delay_secs: float | None = None
    silence_fallback: bool = False
    tools: list[str] = Field(default_factory=list)
    barge_in: bool = False


class Responsiveness(BaseModel):
    reply_latency: Stats = Field(default_factory=Stats)
    stage_medians: dict[str, float] = Field(default_factory=dict)
    tool_turn_latency: Stats = Field(default_factory=Stats)
    first_greeting_secs: float | None = None
    # Time to first byte of Sofia's LLM requests (Pipecat's TTFB metric for the LLM service),
    # one value per request. Compared with reply_latency it shows how much of a turn is the model.
    llm_ttfb: Stats = Field(default_factory=Stats)


class TurnTaking(BaseModel):
    user_turns: int = 0
    false_endpoints: int = 0
    false_endpoint_rate: float | None = None
    endpoint_delay: Stats = Field(default_factory=Stats)
    silence_fallbacks: int = 0
    barge_ins: int = 0
    unsafe_hangup: bool = False
    hangup_cancels: int = 0  # hang-ups cancelled because the candidate spoke
    hangup_wait_secs: float | None = None  # last hangup.armed -> hangup.fired


class Task(BaseModel):
    outcome: str | None = None
    status: str | None = None
    end_reason: str | None = None
    facts_complete: bool = False
    tool_errors: int | None = None
    tool_error_list: list[str] = Field(default_factory=list)
    tool_order_valid: bool | None = None
    tool_order_problems: list[str] = Field(default_factory=list)
    booked_only_if_qualified: bool | None = None
    goodbye_spoken: bool | None = None


class Cost(BaseModel):
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # None = the provider did not report them. Both are parts of the totals above, not extra:
    # see docs/metrics.md for what each provider counts where.
    cache_read_tokens: int | None = None
    reasoning_tokens: int | None = None
    wasted_llm_calls: int = 0
    # LLM requests that failed (`llm.error`), and the times the app asked again after one
    # (`llm.retry`). A retry that worked is a recovered error; see llm/recovery.py.
    llm_errors: int = 0
    llm_retries: int = 0
    tts_chars: int | None = None


class Knowledge(BaseModel):
    """Knowledge base use in the call (docs/metrics.md, "knowledge")."""

    searches: int = 0
    no_match: int = 0
    unavailable: int = 0  # searches that failed: timeout, embedding or store error
    search_ms: Stats = Field(default_factory=Stats)  # handler time per search
    late_results: int = 0  # results delivered after the candidate had spoken again
    questions_referred: int = 0  # saved by Sofia or by finalize


class Frustration(BaseModel):
    """In-call frustration check (docs/metrics.md, "frustration")."""

    checks: int = 0  # judgments with outcome ok
    max_probability: float | None = None
    last_probability: float | None = None
    frustrated_checks: int = 0  # checks at or above the frustration_probability threshold
    errors: int = 0  # judgments that timed out or failed
    notes: int = 0  # notes pushed to Sofia (`frustration.note` events)


class Scorecard(BaseModel):
    screening_id: str
    partial: bool = False  # True when there was no event timeline: task section only
    # True when rebuilt from call_metrics + tool_calls after the Redis events expired: the
    # scalar metrics and tool calls survive, the per-exchange detail does not.
    exchanges_expired: bool = False
    computed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_count: int = 0
    duration_secs: float | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)
    responsiveness: Responsiveness | None = None
    turn_taking: TurnTaking | None = None
    task: Task = Field(default_factory=Task)
    cost: Cost | None = None
    # Voice calls only (system-one turn-taking): judgment counts, latency, actions taken.
    system_one: dict[str, Any] | None = None
    knowledge: Knowledge | None = None
    # Only calls that ran the check (a `frustration.config` event); None otherwise.
    frustration: Frustration | None = None
    exchanges: list[Exchange] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


# --- tool order --------------------------------------------------------------------


def tool_order_problems(calls: Sequence[ToolCall]) -> list[str]:
    """Why the tool sequence is not allowed (empty list = valid).

    Allowed: record_* tools (any order, repeats fine; the one that completes the facts
    returns the verdict) -> list_onboarding_slots (repeatable, only after a record_* result
    that said `qualified: true`, unless the listing itself succeeded: the tool's own gate
    qualified the candidate from facts already on file) -> schedule_onboarding -> end_call,
    which must be the last call. Early exits and the not-qualified path simply skip the
    later steps but still finish with end_call. A failed schedule_onboarding (slot_full...)
    allows another list_onboarding_slots. search_knowledge and refer_to_recruiter are allowed
    anywhere before end_call, outside that sequence. end_call may repeat: a candidate who
    speaks during the hang-up grace window cancels it, and the model ends the call again
    after answering.
    """
    problems: list[str] = []
    qualified = False  # the latest verdict a record_* result carried
    listed = scheduled = False
    ended_at: int | None = None

    for i, call in enumerate(calls):
        name = call.name
        if ended_at is not None:
            if name != "end_call":
                problems.append(f"{name} after end_call")
            continue
        if name in RECORD_TOOLS:
            if scheduled:
                problems.append(f"{name} after schedule_onboarding")
            if call.ok and isinstance(call.result, dict) and "qualified" in call.result:
                qualified = call.result["qualified"] is True
        elif name == "list_onboarding_slots":
            # The tool refuses unless the rule qualifies the candidate, so a listing that
            # succeeded is itself a verdict (a follow-up can start with every fact on file).
            if call.ok and isinstance(call.result, dict) and "error" not in call.result:
                qualified = True
            elif not qualified:
                problems.append("list_onboarding_slots before a qualified result")
            if scheduled:
                problems.append("list_onboarding_slots after schedule_onboarding")
            listed = True
        elif name == "schedule_onboarding":
            if not listed:
                problems.append("schedule_onboarding before list_onboarding_slots")
            if scheduled:
                problems.append("schedule_onboarding twice")
            if call.ok:
                scheduled = True
        elif name in KNOWLEDGE_TOOLS or name == "switch_language":
            pass  # a candidate's question or request can come at any point of the call
        elif name == "end_call":
            if call.ok:
                ended_at = i
        else:
            problems.append(f"unknown tool {name}")
    if ended_at is None:
        problems.append("no successful end_call")
    return problems


def tool_order_valid(calls: Sequence[ToolCall]) -> bool:
    return not tool_order_problems(calls)


# --- timeline extraction -----------------------------------------------------------


def _of(events: Sequence[Event], *types: str) -> list[Event]:
    return [e for e in events if e["type"] in types]


def build_tool_calls(events: Sequence[Event]) -> list[ToolCall]:
    """Merge the started / in_progress / completed events of each tool call."""
    calls: dict[str, ToolCall] = {}
    for e in _of(events, "tool.event"):
        d = e["data"]
        key = d.get("tool_call_id") or f"{d.get('name')}@{e['t']}"
        call = calls.get(key)
        if call is None:
            call = calls[key] = ToolCall(t=e["t"], name=d.get("name", "?"), tool_call_id=key)
        if isinstance(d.get("args"), dict):
            call.args = d["args"]
        kind = d.get("kind", "started")
        call.status = kind
        if d.get("result") is not None:
            call.result = d["result"]
        if d.get("error"):
            call.error = d["error"]
    return list(calls.values())


def _first_after(events: Sequence[Event], t: float, *types: str) -> Event | None:
    return next((e for e in events if e["type"] in types and e["t"] > t), None)


def _call_end(events: Sequence[Event]) -> Event | None:
    ended = _of(events, "call.ended")
    return ended[-1] if ended else None


def _classify_exchanges(
    events: Sequence[Event], th: MetricsThresholds, tool_calls: Sequence[ToolCall]
) -> list[Exchange]:
    ends = _of(events, "user.turn_ended")
    stops = _of(events, "user.speech_stopped")
    predictions = _of(events, "turn_model.prediction")
    exchanges: list[Exchange] = []
    prev_t = float("-inf")

    for i, turn in enumerate(ends):
        t = turn["t"]
        next_t = ends[i + 1]["t"] if i + 1 < len(ends) else float("inf")

        stopped = [e["t"] for e in stops if prev_t < e["t"] <= t]
        endpoint_delay = t - stopped[-1] if stopped else None
        last_pred = [p for p in predictions if prev_t < p["t"] <= t]
        silence_fallback = bool(
            (last_pred and not last_pred[-1]["data"].get("is_complete", True))
            or (endpoint_delay is not None and endpoint_delay >= th.silence_fallback_secs)
        )

        bot = _first_after(events, t, "bot.speech_started")
        resumed = _first_after(events, t, "user.speech_started")
        b = bot["t"] if bot else None
        r = resumed["t"] if resumed else None

        false_endpoint = r is not None and (
            b is None or r < b or r - b < th.false_endpoint_resume_secs
        )
        if false_endpoint:
            kind: ExchangeKind = "false_endpoint"
        elif b is not None:
            kind = "answered"
        else:
            kind = "unanswered"

        # What the bot said for this exchange: the first bot.said after the bot started.
        said = _first_after(events, b, "bot.said") if b is not None else None
        bot_text = said["data"].get("text") if said and said["t"] < next_t else None

        upper = b if b is not None else next_t
        tools = [c.name for c in tool_calls if t < c.t <= upper and c.ran]
        exchanges.append(
            Exchange(
                index=i + 1,
                kind=kind,
                turn_ended_t=_round(t) or 0.0,
                user_text=turn["data"].get("text") or "",
                bot_text=bot_text,
                bot_started_t=_round(b),
                reply_latency_secs=_round(b - stopped[-1]) if (b and stopped) else None,
                endpoint_delay_secs=_round(endpoint_delay),
                silence_fallback=silence_fallback,
                tools=tools,
            )
        )
        prev_t = t

    for _, owner in _barge_ins(events, exchanges):
        if owner is not None:
            owner.barge_in = True
            if owner.kind == "answered":
                owner.kind = "barge_in"
    return exchanges


def _barge_ins(
    events: Sequence[Event], exchanges: Sequence[Exchange]
) -> list[tuple[Event, Exchange | None]]:
    """Interruptions while the bot was speaking, with the exchange they belong to.

    The owner is the latest exchange whose turn ended before the interruption (None for
    an interruption before the first turn ended, e.g. over the greeting). Interruptions
    owned by a false-endpoint exchange are that false endpoint, not a barge-in.
    """
    found: list[tuple[Event, Exchange | None]] = []
    for it in _of(events, "interruption"):
        if not it["data"].get("bot_speaking"):
            continue
        owner = None
        for ex in exchanges:
            if ex.turn_ended_t < it["t"]:
                owner = ex
        if owner is not None and owner.kind == "false_endpoint":
            continue
        found.append((it, owner))
    return found


def _sum_reported(events: Sequence[Event], key: str) -> int | None:
    """Sum of `key` over the events that carry it; None when none of them does."""
    values = [e["data"][key] for e in events if e["data"].get(key) is not None]
    return sum(int(v) for v in values) if values else None


def _wasted_llm_calls(events: Sequence[Event]) -> int:
    """LLM responses cut off before producing bot audio or a tool call.

    The window of a response starts at llm.started and ends at the earliest of the next
    llm.started, interruption, user.turn_started, or call end. It is wasted when the window
    ended by an interruption / new user turn and contains no bot.speech_started and no
    tool.event: a tool-only response is real work, not waste. llm.ended is deliberately not
    the window end because bot audio starts after it (TTS lag).
    """
    wasted = 0
    end = _call_end(events)
    call_end_t = end["t"] if end else float("inf")
    for e in _of(events, "llm.started"):
        s = e["t"]
        next_llm = _first_after(events, s, "llm.started")
        cutter = _first_after(events, s, "interruption", "user.turn_started")
        if cutter is None:
            continue
        stop = min(cutter["t"], next_llm["t"] if next_llm else float("inf"), call_end_t)
        if stop != cutter["t"]:
            continue
        produced = any(
            x["type"] in ("bot.speech_started", "tool.event") and s < x["t"] <= stop for x in events
        )
        if not produced:
            wasted += 1
    return wasted


def _unsafe_hangup(
    events: Sequence[Event], calls: Sequence[ToolCall], th: MetricsThresholds
) -> bool:
    fired = _of(events, "hangup.fired")
    if fired:
        end_t = fired[-1]["t"]  # the actual disconnect decision
    elif _of(events, "hangup.armed"):
        return False  # armed but never fired: the candidate hung up first, nothing was cut
    else:
        # Legacy timeline (no hang-up events): the end_call tool decision time.
        ended = [
            c
            for c in calls
            if c.name == "end_call"
            and c.status != "cancelled"
            and not (c.status == "completed" and not c.ok)
        ]
        if not ended:
            return False
        end_t = ended[-1].t
    stops = [e["t"] for e in _of(events, "user.speech_stopped") if e["t"] <= end_t]
    starts = [e["t"] for e in _of(events, "user.speech_started") if e["t"] <= end_t]
    last_stop = stops[-1] if stops else None
    last_start = starts[-1] if starts else None
    if last_start is not None and (last_stop is None or last_start > last_stop):
        return True  # the user was mid-speech
    return last_stop is not None and end_t - last_stop < th.unsafe_hangup_secs


def _hangup_wait(events: Sequence[Event]) -> float | None:
    fired = _of(events, "hangup.fired")
    if not fired:
        return None
    armed = [e["t"] for e in _of(events, "hangup.armed") if e["t"] <= fired[-1]["t"]]
    return fired[-1]["t"] - armed[-1] if armed else None


def _goodbye_spoken(events: Sequence[Event]) -> bool | None:
    """Heuristic: the last bot.said before call end contains a farewell word."""
    end = _call_end(events)
    limit = end["t"] if end else float("inf")
    said = [e for e in _of(events, "bot.said") if e["t"] <= limit]
    if not said:
        return None
    text = _fold(said[-1]["data"].get("text") or "")
    return any(re.search(rf"\b{re.escape(_fold(w))}\b", text) for w in FAREWELL_WORDS)


def _last_end_reason(events: Sequence[Event]) -> str | None:
    end = _call_end(events)
    return end["data"].get("end_reason") if end else None


def _booked(screening: Screening, calls: Sequence[ToolCall]) -> bool:
    return bool(screening.slot_id) or any(c.name == "schedule_onboarding" and c.ok for c in calls)


def _last_verdict(calls: Sequence[ToolCall]) -> bool | None:
    """The latest qualification verdict the tools gave.

    A record_* tool returns `qualified` once the facts are complete. A successful
    list_onboarding_slots is a verdict too: the tool refuses unless the rule says the
    candidate qualifies. That covers a follow-up call that starts with every fact on file,
    where nothing is recorded and no record_* result carries `qualified`.
    """
    verdict: bool | None = None
    for c in calls:
        if not c.ok or not isinstance(c.result, dict):
            continue
        if c.name in RECORD_TOOLS and "qualified" in c.result:
            verdict = bool(c.result["qualified"])
        elif c.name == "list_onboarding_slots" and "error" not in c.result:
            verdict = True
    return verdict


def _tool_error_text(call: ToolCall) -> str:
    if call.error:
        return call.error
    if isinstance(call.result, dict) and "error" in call.result:
        return str(call.result["error"])
    return call.status


def task_from_state(screening: Screening, facts: ScreeningFacts) -> Task:
    """The task fields that need only database state (no event timeline)."""
    return Task(
        outcome=screening.outcome.value if screening.outcome else None,
        status=screening.status.value,
        facts_complete=not missing_questions(facts),
    )


def knowledge_from_events(events: Sequence[Event]) -> Knowledge:
    searches = [e["data"] for e in _of(events, "kb_search")]
    times = [d["total_ms"] for d in searches if d.get("total_ms") is not None]
    return Knowledge(
        searches=len(searches),
        no_match=sum(1 for d in searches if d.get("no_match") is True),
        unavailable=sum(1 for d in searches if d.get("error")),
        search_ms=Stats.of(times),
        late_results=sum(
            1 for e in _of(events, "kb_result_delivered") if e["data"].get("mode") == "deferred"
        ),
        questions_referred=len(_of(events, "question_referred")),
    )


def frustration_from_events(events: Sequence[Event], th: MetricsThresholds) -> Frustration | None:
    if not _of(events, "frustration.config"):
        return None  # the check did not run in this call: not the same as zero checks
    judgments = [e["data"] for e in _of(events, "frustration.judgment")]
    ok = [
        d["probability"]
        for d in judgments
        if d.get("outcome") == "ok" and d.get("probability") is not None
    ]
    return Frustration(
        checks=len(ok),
        max_probability=max(ok) if ok else None,
        last_probability=ok[-1] if ok else None,
        frustrated_checks=sum(1 for p in ok if p >= th.frustration_probability),
        errors=len(judgments) - len(ok),
        notes=len(_of(events, "frustration.note")),
    )


# --- main entry --------------------------------------------------------------------


def compute_scorecard(
    events: Sequence[Event],
    screening: Screening,
    facts: ScreeningFacts,
    thresholds: MetricsThresholds | None = None,
) -> Scorecard:
    th = thresholds or MetricsThresholds()
    events = sorted(events, key=lambda e: e["t"])  # stable: keeps arrival order on ties
    task = task_from_state(screening, facts)
    card = Scorecard(
        screening_id=screening.id,
        event_count=len(events),
        thresholds={
            "false_endpoint_resume_secs": th.false_endpoint_resume_secs,
            "unsafe_hangup_secs": th.unsafe_hangup_secs,
            "silence_fallback_secs": th.silence_fallback_secs,
            "frustration_probability": th.frustration_probability,
        },
        task=task,
    )
    if not events:
        card.partial = True
        return card

    card.duration_secs = _round(events[-1]["t"])
    calls = build_tool_calls(events)
    card.tool_calls = calls
    exchanges = _classify_exchanges(events, th, calls)
    card.exchanges = exchanges

    # responsiveness
    answered = [x for x in exchanges if x.kind in ("answered", "barge_in")]
    latencies = [x.reply_latency_secs for x in answered if x.reply_latency_secs is not None]
    tool_lat = [
        x.reply_latency_secs for x in answered if x.tools and x.reply_latency_secs is not None
    ]
    per_stage: dict[str, list[float]] = {}
    for e in _of(events, "latency.breakdown"):
        if e["data"].get("measured_from") not in (None, "user_silence"):
            continue  # the greeting breakdown is timed from connect, not from user silence
        for key, secs in (e["data"].get("stages") or {}).items():
            per_stage.setdefault(key, []).append(secs)
    connected = next(iter(_of(events, "call.connected")), None)
    first_bot = next(iter(_of(events, "bot.speech_started")), None)
    greeting = (
        first_bot["t"] - connected["t"]
        if connected and first_bot and first_bot["t"] >= connected["t"]
        else None
    )
    card.responsiveness = Responsiveness(
        reply_latency=Stats.of(latencies),
        stage_medians={k: round(median(v), 3) for k, v in sorted(per_stage.items())},
        tool_turn_latency=Stats.of(tool_lat),
        first_greeting_secs=_round(greeting),
        llm_ttfb=Stats.of([float(e["data"]["seconds"]) for e in _of(events, "llm.ttfb")]),
    )

    # turn taking
    false_eps = sum(1 for x in exchanges if x.kind == "false_endpoint")
    delays = [x.endpoint_delay_secs for x in exchanges if x.endpoint_delay_secs is not None]
    card.turn_taking = TurnTaking(
        user_turns=len(exchanges),
        false_endpoints=false_eps,
        false_endpoint_rate=_round(false_eps / len(exchanges)) if exchanges else None,
        endpoint_delay=Stats.of(delays),
        silence_fallbacks=sum(1 for x in exchanges if x.silence_fallback),
        barge_ins=len(_barge_ins(events, exchanges)),
        unsafe_hangup=_unsafe_hangup(events, calls, th),
        hangup_cancels=len(_of(events, "hangup.canceled")),
        hangup_wait_secs=_round(_hangup_wait(events)),
    )

    # task
    errors = [
        f"{c.name}: {_tool_error_text(c)}"
        for c in calls
        if c.status in ("failed", "timed_out")
        or (c.status == "completed" and isinstance(c.result, dict) and "error" in c.result)
    ]
    task.end_reason = _last_end_reason(events)
    task.tool_errors = len(errors)
    task.tool_error_list = errors
    ran = [c for c in calls if c.ran]
    task.tool_order_problems = tool_order_problems(ran)
    task.tool_order_valid = not task.tool_order_problems
    if _booked(screening, ran):
        task.booked_only_if_qualified = _last_verdict(ran) is True
    else:
        task.booked_only_if_qualified = True  # nothing booked, nothing to violate
    task.goodbye_spoken = _goodbye_spoken(events)

    # cost
    usage = _of(events, "llm.usage")
    tts = _of(events, "tts.chars")
    card.cost = Cost(
        llm_calls=len(_of(events, "llm.started")),
        prompt_tokens=sum(int(e["data"].get("prompt_tokens") or 0) for e in usage),
        completion_tokens=sum(int(e["data"].get("completion_tokens") or 0) for e in usage),
        cache_read_tokens=_sum_reported(usage, "cache_read_tokens"),
        reasoning_tokens=_sum_reported(usage, "reasoning_tokens"),
        wasted_llm_calls=_wasted_llm_calls(events),
        llm_errors=len(_of(events, "llm.error")),
        llm_retries=len(_of(events, "llm.retry")),
        tts_chars=sum(int(e["data"].get("chars") or 0) for e in tts) if tts else None,
    )
    card.system_one = summarize_events(events)
    card.knowledge = knowledge_from_events(events)
    card.frustration = frustration_from_events(events, th)
    return card


# --- persistence mapping -----------------------------------------------------------
# The call_metrics row holds the scalar scorecard (typed columns); the tool_calls rows hold
# the tool calls that ran. Per-exchange detail, stage medians, endpoint-delay stats, hang-up
# cancels, error/problem lists and thresholds are not stored: the lists are recomputed from
# the tool calls, the rest needs the event timeline (while Redis still has it).


def metrics_row(card: Scorecard) -> dict[str, Any]:
    """The call_metrics columns for `card` (without screening_id)."""
    r, t, cost, kb = card.responsiveness, card.turn_taking, card.cost, card.knowledge
    fr = card.frustration
    return {
        "computed_at": datetime.fromisoformat(card.computed_at),
        "partial": card.partial,
        "event_count": card.event_count,
        "duration_secs": card.duration_secs,
        "reply_p50": r.reply_latency.p50 if r else None,
        "reply_p95": r.reply_latency.p95 if r else None,
        "reply_max": r.reply_latency.max if r else None,
        "tool_turn_p50": r.tool_turn_latency.p50 if r else None,
        "first_greeting_secs": r.first_greeting_secs if r else None,
        "llm_ttfb_p50": r.llm_ttfb.p50 if r else None,
        "llm_ttfb_p95": r.llm_ttfb.p95 if r else None,
        "user_turns": t.user_turns if t else None,
        "false_endpoints": t.false_endpoints if t else None,
        "barge_ins": t.barge_ins if t else None,
        "silence_fallbacks": t.silence_fallbacks if t else None,
        "unsafe_hangup": t.unsafe_hangup if t else None,
        "hangup_wait_secs": t.hangup_wait_secs if t else None,
        "facts_complete": card.task.facts_complete,
        "tool_errors": card.task.tool_errors,
        "tool_order_valid": card.task.tool_order_valid,
        "booked_only_if_qualified": card.task.booked_only_if_qualified,
        "goodbye_spoken": card.task.goodbye_spoken,
        "end_reason": card.task.end_reason,
        "llm_calls": cost.llm_calls if cost else None,
        "prompt_tokens": cost.prompt_tokens if cost else None,
        "completion_tokens": cost.completion_tokens if cost else None,
        "cache_read_tokens": cost.cache_read_tokens if cost else None,
        "reasoning_tokens": cost.reasoning_tokens if cost else None,
        "wasted_llm_calls": cost.wasted_llm_calls if cost else None,
        "llm_errors": cost.llm_errors if cost else None,
        "llm_retries": cost.llm_retries if cost else None,
        "tts_chars": cost.tts_chars if cost else None,
        "kb_searches": kb.searches if kb else None,
        "kb_no_match": kb.no_match if kb else None,
        "kb_unavailable": kb.unavailable if kb else None,
        "kb_search_p50_ms": kb.search_ms.p50 if kb else None,
        "kb_search_max_ms": kb.search_ms.max if kb else None,
        "kb_late_results": kb.late_results if kb else None,
        "questions_referred": kb.questions_referred if kb else None,
        "frustration_checks": fr.checks if fr else None,
        "frustration_max": fr.max_probability if fr else None,
        "frustration_frustrated_checks": fr.frustrated_checks if fr else None,
        "frustration_notes": fr.notes if fr else None,
    }


def _stored_error(call: ToolCall) -> str | None:
    """The error text worth storing: None for a call that worked or is merely unfinished."""
    if call.ok:
        return None
    if call.error:
        return call.error
    if isinstance(call.result, dict) and "error" in call.result:
        return str(call.result["error"])
    return call.status if call.status in ("failed", "timed_out") else None


def tool_call_rows(calls: Sequence[ToolCall]) -> list[dict[str, Any]]:
    """The tool_calls columns (without screening_id) for the calls that ran, in order."""
    return [
        {
            "seq": seq,
            "t": _round(c.t) or 0.0,
            "name": c.name,
            "args": c.args,
            "result": c.result,
            "ok": c.ok,
            "error": _stored_error(c),
        }
        for seq, c in enumerate(c for c in calls if c.ran)
    ]


def _stored_status(row: Mapping[str, Any]) -> str:
    if row["ok"] or row["result"] is not None:
        return "completed"
    return "failed" if row["error"] else "in_progress"


def tool_calls_from_rows(rows: Sequence[Mapping[str, Any]]) -> list[ToolCall]:
    return [
        ToolCall(
            t=row["t"],
            name=row["name"],
            args=row["args"] or {},
            result=row["result"],
            # `ok` is derived from status + result: a call with a result completed, one that
            # left only an error failed, one with neither never finished.
            status=_stored_status(row),
            error=row["error"],
        )
        for row in rows
    ]


def scorecard_from_stored(
    screening: Screening, row: Mapping[str, Any], calls: Sequence[ToolCall]
) -> Scorecard:
    """A scorecard from the stored row and tool calls: everything except the exchanges."""
    partial = bool(row["partial"])
    task = Task(
        outcome=screening.outcome.value if screening.outcome else None,
        status=screening.status.value,
        end_reason=row["end_reason"],
        facts_complete=row["facts_complete"],
        tool_errors=row["tool_errors"],
        tool_error_list=[
            f"{c.name}: {_tool_error_text(c)}"
            for c in calls
            if c.status in ("failed", "timed_out") or (c.status == "completed" and not c.ok)
        ],
        tool_order_valid=row["tool_order_valid"],
        tool_order_problems=[] if partial else tool_order_problems(calls),
        booked_only_if_qualified=row["booked_only_if_qualified"],
        goodbye_spoken=row["goodbye_spoken"],
    )
    card = Scorecard(
        screening_id=screening.id,
        partial=partial,
        exchanges_expired=not partial,
        computed_at=row["computed_at"].isoformat(),
        event_count=row["event_count"],
        duration_secs=row["duration_secs"],
        task=task,
        tool_calls=list(calls),
    )
    if partial:
        return card
    card.responsiveness = Responsiveness(
        reply_latency=Stats(p50=row["reply_p50"], p95=row["reply_p95"], max=row["reply_max"]),
        tool_turn_latency=Stats(p50=row["tool_turn_p50"]),
        first_greeting_secs=row["first_greeting_secs"],
        llm_ttfb=Stats(p50=row["llm_ttfb_p50"], p95=row["llm_ttfb_p95"]),
    )
    card.turn_taking = TurnTaking(
        user_turns=row["user_turns"] or 0,
        false_endpoints=row["false_endpoints"] or 0,
        silence_fallbacks=row["silence_fallbacks"] or 0,
        barge_ins=row["barge_ins"] or 0,
        unsafe_hangup=bool(row["unsafe_hangup"]),
        hangup_wait_secs=row["hangup_wait_secs"],
    )
    card.cost = Cost(
        llm_calls=row["llm_calls"] or 0,
        prompt_tokens=row["prompt_tokens"] or 0,
        completion_tokens=row["completion_tokens"] or 0,
        cache_read_tokens=row["cache_read_tokens"],
        reasoning_tokens=row["reasoning_tokens"],
        wasted_llm_calls=row["wasted_llm_calls"] or 0,
        llm_errors=row["llm_errors"] or 0,
        llm_retries=row["llm_retries"] or 0,
        tts_chars=row["tts_chars"],
    )
    card.knowledge = Knowledge(
        searches=row["kb_searches"] or 0,
        no_match=row["kb_no_match"] or 0,
        unavailable=row["kb_unavailable"] or 0,
        search_ms=Stats(
            count=row["kb_searches"] or 0, p50=row["kb_search_p50_ms"], max=row["kb_search_max_ms"]
        ),
        late_results=row["kb_late_results"] or 0,
        questions_referred=row["questions_referred"] or 0,
    )
    if row["frustration_checks"] is not None:  # NULL: the check did not run in that call
        card.frustration = Frustration(
            checks=row["frustration_checks"],
            max_probability=row["frustration_max"],
            frustrated_checks=row["frustration_frustrated_checks"] or 0,
            notes=row["frustration_notes"] or 0,
        )
    return card
