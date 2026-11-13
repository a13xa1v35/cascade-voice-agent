"""Drop control: when does the simulated candidate hang up (or get superseded)?

This lives in the harness, never in the simulator: the harness watches the database and the
tool activity and acts the moment a scenario's condition holds, exactly like a dropped
connection would. Conditions are pure functions of a `CallState` snapshot so they can be unit
tested against a fake state.

"Facts" are the seven `ScreeningFacts` fields, one per record_* tool (subjects and levels,
availability and teaching format are separate facts, each saved by its own tool).

Tool activity is observed one level below the tools: `ObservedStore` notes the store call
each tool makes (set_experience <- record_experience, list_open_slots <-
list_onboarding_slots, book_slot <- schedule_onboarding). That is the same moment the tool's
effect happens, without touching the call pipeline.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from hr_screener.models import ScreeningFacts
from hr_screener.storage.store import ScreeningStore

FACT_FIELDS = (
    "start_date",
    "subjects",
    "levels",
    "availability",
    "teaching_format",
    "work_authorized",
    "experience",
)
# The record tool that writes each fact field.
FIELD_TOOL = {
    "start_date": "record_start_date",
    "subjects": "record_subjects",
    "levels": "record_levels",
    "availability": "record_availability",
    "teaching_format": "record_teaching_format",
    "work_authorized": "record_work_authorization",
    "experience": "record_experience",
}
TOOL_FIELD = {tool: name for name, tool in FIELD_TOOL.items()}


def fact_fields(facts: ScreeningFacts) -> set[str]:
    """Which of the seven facts are saved (a field counts when it is set / non-empty)."""
    present = {
        "start_date": facts.start_date is not None,
        "subjects": bool(facts.subjects),
        "levels": bool(facts.levels),
        "availability": bool(facts.availability),
        "teaching_format": facts.teaching_format is not None,
        "work_authorized": facts.work_authorized is not None,
        "experience": facts.experience is not None,
    }
    return {name for name, ok in present.items() if ok}


@dataclass(frozen=True)
class CallState:
    """What a drop condition can see: the saved facts, how many candidate lines Sofia has
    fully answered, and which tools have run (by store effect) in this call."""

    facts: frozenset[str]
    candidate_turns: int
    tools_seen: frozenset[str]


class DropCondition(Protocol):
    @property
    def description(self) -> str: ...

    def satisfied(self, state: CallState) -> bool: ...


@dataclass(frozen=True)
class AfterTurnsNoFacts:
    """After Sofia answered `turns` candidate lines and no fact is saved yet."""

    turns: int

    @property
    def description(self) -> str:
        return f"after {self.turns} candidate turns with no facts saved"

    def satisfied(self, state: CallState) -> bool:
        return state.candidate_turns >= self.turns and not state.facts


@dataclass(frozen=True)
class AfterFacts:
    """As soon as `count` facts are saved (carried-over facts count)."""

    count: int

    @property
    def description(self) -> str:
        return f"after {self.count} facts saved"

    def satisfied(self, state: CallState) -> bool:
        return len(state.facts) >= self.count


@dataclass(frozen=True)
class AvailabilityWithoutFormat:
    """record_availability saved, record_teaching_format not yet."""

    description: str = "availability saved but no teaching format"

    def satisfied(self, state: CallState) -> bool:
        return "availability" in state.facts and "teaching_format" not in state.facts


@dataclass(frozen=True)
class SubjectsWithoutLevels:
    """record_subjects saved, record_levels not yet."""

    description: str = "subjects saved but no levels"

    def satisfied(self, state: CallState) -> bool:
        return "subjects" in state.facts and "levels" not in state.facts


@dataclass(frozen=True)
class AfterTool:
    """Once the named tool ran in this call (observed through its store effect)."""

    tool: str

    @property
    def description(self) -> str:
        return f"after {self.tool}"

    def satisfied(self, state: CallState) -> bool:
        return self.tool in state.tools_seen


# store method -> the tool that calls it
_STORE_TOOL = {
    "set_start_date": "record_start_date",
    "set_subjects": "record_subjects",
    "set_levels": "record_levels",
    "set_availability": "record_availability",
    "set_teaching_format": "record_teaching_format",
    "set_work_authorized": "record_work_authorization",
    "set_experience": "record_experience",
    "list_open_slots": "list_onboarding_slots",
    "book_slot": "schedule_onboarding",
}


@dataclass
class ToolActivity:
    seen: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def note(self, screening_id: str, tool: str) -> None:
        self.seen[screening_id].append(tool)


class ObservedStore(ScreeningStore):
    """A ScreeningStore that notes which tool-backed writes/reads happen per screening.
    Behaviour is unchanged; the harness only reads `activity`."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.activity = ToolActivity()
        # Screenings on a live call. list_open_slots has no screening argument, so the
        # harness registers who is on a call (the tools call it after their qualification gate).
        self.live: set[str] = set()

    async def set_start_date(self, screening_id, start_date):
        await super().set_start_date(screening_id, start_date)
        self.activity.note(screening_id, _STORE_TOOL["set_start_date"])

    async def set_subjects(self, screening_id, subjects):
        await super().set_subjects(screening_id, subjects)
        self.activity.note(screening_id, _STORE_TOOL["set_subjects"])

    async def set_levels(self, screening_id, levels):
        await super().set_levels(screening_id, levels)
        self.activity.note(screening_id, _STORE_TOOL["set_levels"])

    async def set_availability(self, screening_id, availability):
        await super().set_availability(screening_id, availability)
        self.activity.note(screening_id, _STORE_TOOL["set_availability"])

    async def set_teaching_format(self, screening_id, teaching_format):
        await super().set_teaching_format(screening_id, teaching_format)
        self.activity.note(screening_id, _STORE_TOOL["set_teaching_format"])

    async def set_work_authorized(self, screening_id, authorized):
        await super().set_work_authorized(screening_id, authorized)
        self.activity.note(screening_id, _STORE_TOOL["set_work_authorized"])

    async def set_experience(self, screening_id, experience):
        await super().set_experience(screening_id, experience)
        self.activity.note(screening_id, _STORE_TOOL["set_experience"])

    async def list_open_slots(self, after, limit=10):
        slots = await super().list_open_slots(after, limit)
        for screening_id in self.live:
            self.activity.note(screening_id, _STORE_TOOL["list_open_slots"])
        return slots

    async def book_slot(self, screening_id, slot_id):
        result = await super().book_slot(screening_id, slot_id)
        self.activity.note(screening_id, _STORE_TOOL["book_slot"])
        return result


async def snapshot(store: ObservedStore, screening_id: str, candidate_turns: int) -> CallState:
    facts = await store.get_facts(screening_id)
    return CallState(
        facts=frozenset(fact_fields(facts)),
        candidate_turns=candidate_turns,
        tools_seen=frozenset(store.activity.seen.get(screening_id, ())),
    )
