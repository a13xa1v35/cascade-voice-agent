"""Plain data for one eval conversation: what happened, as JSON-friendly dataclasses.

`RunRecord` is what `runs.jsonl` stores (one line per conversation) and what the hard checks
read, so checks and the report are pure functions of it and can be tested with canned records.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from evals.common.usage import Usage


@dataclass
class Turn:
    role: str  # "agent" | "candidate"
    text: str


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    result: Any
    status: str
    ok: bool


@dataclass
class DriftTurn:
    """Language detection of one Sofia turn (all turns are stored; `drifted` marks the bad)."""

    turn: int  # index into the call's Sofia turns
    lang: str
    es_hits: int
    en_hits: int
    drifted: bool
    text: str
    at: float = 0.0  # epoch seconds the reply reached the harness (to place it around a switch)


@dataclass
class CallRecord:
    index: int  # 1-based position among the live calls of the scenario
    screening_id: str
    attempt: int
    previous_screening_id: str | None
    mode: str  # fresh | followup | closed_booked | closed_rejected
    facts_at_start: dict[str, Any]  # what the call started with (after new_screening)
    fields_at_start: list[str]  # which of the seven facts were saved at start
    status: str | None = None
    outcome: str | None = None
    end_reason: str | None = None
    # drop condition text | "agent" | "superseded by next call" | "max_turns" | "timeout"
    ended_by: str = ""
    slot_id: str | None = None
    transcript: list[Turn] = field(default_factory=list)  # as the harness saw it (live)
    saved_transcript: list[dict[str, str]] = field(default_factory=list)  # as the store has it
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    facts_end: dict[str, Any] = field(default_factory=dict)
    drift: list[DriftTurn] = field(default_factory=list)
    summary_source: str | None = None
    # Sofia sent no reply within reply_timeout_secs: the candidate was left in silence. A Sofia
    # failure (check `responsive`), not an invalid run.
    unresponsive: bool = False
    # The texts of every error Sofia's LLM service reported during the call, oldest first
    # (recovered ones included), and how many times the app asked the model again after one.
    llm_errors: list[str] = field(default_factory=list)
    llm_retries: int = 0
    # Events of the call from the Redis timeline, oldest first, as {"type", "t", "data"}: in
    # knowledge scenarios `kb_search`, `kb_result_delivered`, `kb_holding_line`,
    # `question_referred`; in frustration-note scenarios `frustration.*` and `tool.event`
    # (`harness.keeps_event`). The holding line is only here: it is not in `saved_transcript`
    # (it is kept out of the LLM context).
    events: list[dict[str, Any]] = field(default_factory=list)
    # Rows of the `referred_questions` table for this call's screening (JSON-friendly).
    referred_questions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def llm_errors_recovered(self) -> int:
        """Failed requests the app's retry got past. Not counted once the call was given up
        (end reason `llm_error`) or left in silence: then the retry did not help."""
        if self.unresponsive or self.end_reason == "llm_error":
            return 0
        return self.llm_retries


def events_of(call: CallRecord, *types: str) -> list[dict[str, Any]]:
    """The call's recorded events of the given types (`kb_events` payloads are `e["data"]`)."""
    return [e for e in call.events if e["type"] in types]


def other_language(language: str) -> str:
    return "en" if language == "es" else "es"


def split_at_switch(
    call: CallRecord,
) -> tuple[list[DriftTurn], DriftTurn | None, list[DriftTurn]] | None:
    """Sofia's turns of a call split at its `language_switched` event: the turns before it, the
    first turn after it (the one that carries the switch: text said around the tool call is
    delivered with it, so it may mix both languages) and the turns after that. None when the
    call has no such event. Needs the event (kept in `Expect.language_switch` scenarios) and
    `DriftTurn.at`; the recorder's `wall` and `at` come from the same machine clock."""
    switched = events_of(call, "language_switched")
    if not switched:
        return None
    when = datetime.fromisoformat(switched[0]["wall"]).timestamp()
    before = [d for d in call.drift if d.at < when]
    after = [d for d in call.drift if d.at >= when]
    return before, (after[0] if after else None), after[1:]


def mark_switch_drift(call: CallRecord, start_language: str) -> None:
    """Re-judge `DriftTurn.drifted` for a call that switched language: turns before the switch
    must be in the start language, turns after it in the other one, and the turn that carries
    the switch is not judged. A call that did not switch is left as the harness marked it."""
    parts = split_at_switch(call)
    if parts is None:
        return
    before, carrier, after = parts
    for expected, turns in ((start_language, before), (other_language(start_language), after)):
        for d in turns:
            d.drifted = d.lang in ("mixed", "en", "es") and d.lang != expected
    if carrier is not None:
        carrier.drifted = False


def search_outcome(data: dict[str, Any]) -> str:
    """How one `kb_search` event ended: found | no_match | unavailable."""
    if data.get("error"):
        return "unavailable"
    return "found" if data.get("chunk_ids") else "no_match"


COMPONENTS = ("agent", "simulator", "judge", "summary")


@dataclass
class JudgeVerdict:
    id: str
    answer: str  # "yes" | "no" | "n/a"
    evidence: str
    call: int | None = None  # 1-based call the evidence is from
    # The judge's quote was not found in that call's transcript, so `evidence` was blanked
    # (hr_screener.citations): a verdict is never shown with words nobody said.
    evidence_dropped: bool = False


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class RunRecord:
    scenario: str
    language: str
    run: int
    persona: str
    today: str
    agent_model: str
    summary_enabled: bool
    agent_provider: str = "anthropic"
    # ok | trigger_missed | did_not_finish (30 turns) | provider_quota | simulator_drift | error
    # (no reply in time is not here: it is `CallRecord.unresponsive`, a Sofia failure)
    harness_status: str = "ok"
    harness_detail: str = ""
    calls: list[CallRecord] = field(default_factory=list)
    # screenings of the candidate, oldest first (setup ones included)
    screenings: list[dict[str, Any]] = field(default_factory=list)
    bookings: list[dict[str, Any]] = field(default_factory=list)  # {screening_id, slot_id}
    # bookings that existed before the first live call (setup state)
    bookings_before: list[dict[str, Any]] = field(default_factory=list)
    final_facts: dict[str, Any] = field(default_factory=dict)
    expected_facts: dict[str, Any] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    judge: list[JudgeVerdict] = field(default_factory=list)
    judge_error: str = ""
    kb_mode: str = ""  # "" (no knowledge base) | real | slow | down
    # Chunks the searches returned, id -> {title, kind, as_of, text}: what the judge reads to
    # decide whether Sofia's answer stayed inside the returned text.
    kb_chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    usage: dict[str, Usage] = field(default_factory=lambda: {c: Usage() for c in COMPONENTS})
    # Time to first byte of every request Sofia's LLM made in this run (all its calls), seconds.
    llm_ttfb_secs: list[float] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def valid(self) -> bool:
        return self.harness_status == "ok"

    @property
    def passed(self) -> bool:
        return self.valid and all(c.passed for c in self.checks)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
