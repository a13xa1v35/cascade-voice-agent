"""The texts the model reads. Every `{...}` placeholder in the texts that still use `fmt`
resolves, every branch of the two system-prompt templates renders (an eval would not reach the
rare ones), and the fixed part of the system prompt never depends on the call (the prompt cache
needs it byte-identical)."""

import string
from datetime import UTC, date, datetime, timedelta

from hr_screener.agent import prompt_text
from hr_screener.agent.prompt_text import LANGUAGE_RULE, PROMPT, RESULTS, TOOLS
from hr_screener.agent.prompts import build_system_prompt_parts
from hr_screener.config import Settings
from hr_screener.models import (
    Availability,
    CallSummary,
    Candidate,
    Level,
    OnboardingSlot,
    Opening,
    Outcome,
    ReferredQuestion,
    Role,
    ScreeningFacts,
    SlotMode,
    Subject,
    TeachingFormat,
)
from hr_screener.screening.followup import ClosedContext, EndedHow, FollowUpContext

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def all_texts() -> list[str]:
    texts = [*PROMPT.values(), *LANGUAGE_RULE.values(), *RESULTS.values()]
    for tool in [*TOOLS.values(), prompt_text.END_CALL_CLOSED]:
        texts += [tool.name, tool.description]
        for param in tool.params.values():
            texts += [param.name, param.description]
    return texts


def test_placeholders_resolve():
    """Every `{...}` in a text is a known reference or one of the values the callers pass."""
    known = set(prompt_text.refs()) | {
        "language", "first_name", "kb_language", "subjects", "levels", "availability", "format",
    }  # fmt: skip
    for text in all_texts():
        fields = {f for _, f, _, _ in string.Formatter().parse(text) if f}
        assert fields <= known, fields - known


# --- the system prompt templates -------------------------------------------------------------

OPENING = Opening(id="o1", role=Role.TUTOR, location="Madrid", subjects=[Subject.MATH])
OPENING_NO_SUBJECTS = Opening(id="o2", role=Role.TUTOR, location="Sevilla", subjects=[])
CANDIDATE = Candidate(
    name="Maria Lopez", phone="+34", location="Madrid", opening_id="o1", subjects=[Subject.MATH]
)
CANDIDATE_NO_SUBJECTS = Candidate(name="Jo Doe", phone="+34", location="Cadiz", opening_id="o1")
SLOT = OnboardingSlot(
    starts_at=datetime(2026, 11, 12, 16, tzinfo=UTC), mode=SlotMode.IN_PERSON, address="Chamberi"
)
SLOT_PAST = OnboardingSlot(starts_at=datetime(2026, 11, 8, 16, tzinfo=UTC), mode=SlotMode.ONLINE)
ALL = ScreeningFacts(
    start_date=date(2026, 11, 20),
    subjects=[Subject.MATH],
    levels=[Level.PRIMARY],
    availability=[Availability.WORKDAYS_MORNING],
    teaching_format=TeachingFormat.BOTH,
    work_authorized=True,
    experience="Five years",
)
SUMMARY = CallSummary(key_points=["a"], candidate_questions=["b?"], language="en", source="llm")
FALLBACK = SUMMARY.model_copy(update={"source": "fallback"})
REFERRED = ReferredQuestion(screening_id="s", question="q?", automatic=False, language="en")


def followup(
    ended: EndedHow = EndedHow.DROPPED,
    ago: timedelta = timedelta(days=2),
    note: str | None = None,
    summary: CallSummary | None = None,
    referred: tuple[ReferredQuestion, ...] = (),
    stale: date | None = None,
    facts: ScreeningFacts | None = None,
) -> FollowUpContext:
    facts = facts or ScreeningFacts()
    return FollowUpContext("prev", 2, NOW - ago, ended, note, summary, facts, stale, referred)


# One call per branch of screening.j2: every ended-how, every half-answered question, every
# question text, every interest step, the verdicts, the summary / referred / stale parts.
FOLLOWUPS = [
    followup(EndedHow.DROPPED),
    followup(EndedHow.NO_ANSWER),
    followup(EndedHow.CALLBACK_REQUESTED, note="after five"),
    followup(EndedHow.CALLBACK_REQUESTED),
    # subjects without levels, levels without subjects, slots without format, format without slots
    followup(facts=ScreeningFacts(subjects=[Subject.MATH], start_date=ALL.start_date)),
    followup(facts=ScreeningFacts(levels=[Level.PRIMARY])),
    followup(facts=ScreeningFacts(availability=[Availability.SATURDAY_MORNING])),
    followup(facts=ScreeningFacts(teaching_format=TeachingFormat.ONLINE)),
    followup(
        summary=SUMMARY,
        referred=(REFERRED,),
        ago=timedelta(minutes=1),
        facts=ScreeningFacts(subjects=[Subject.MATH]),
    ),
    followup(summary=FALLBACK, stale=date(2026, 11, 1)),
    followup(facts=ALL.model_copy(update={"experience": None})),
    followup(facts=ALL),  # nothing missing, qualified
    followup(facts=ALL.model_copy(update={"subjects": [Subject.ENGLISH]})),  # not qualified
]


def render_all() -> list[str]:
    """Every branch of both templates, under StrictUndefined."""
    settings = Settings(_env_file=None, timezone="UTC")
    calls = [
        (CANDIDATE, OPENING, None, None),
        (CANDIDATE_NO_SUBJECTS, OPENING_NO_SUBJECTS, None, None),
    ]
    calls += [(CANDIDATE, OPENING, fu, None) for fu in FOLLOWUPS]
    calls += [
        (
            CANDIDATE_NO_SUBJECTS,
            OPENING,
            followup(facts=ScreeningFacts(levels=[Level.PRIMARY])),
            None,
        )
    ]
    for slot, outcome in (
        (SLOT, Outcome.SCHEDULED),
        (SLOT_PAST, Outcome.SCHEDULED),
        (None, Outcome.SCHEDULED),
        (None, Outcome.NOT_QUALIFIED),
    ):
        calls.append((CANDIDATE, OPENING, None, ClosedContext("s0", outcome, NOW, slot)))
    rendered = []
    for language in ("en", "es"):
        s = settings.model_copy(update={"language": language})
        for candidate, opening, fu, closed in calls:
            for knowledge in (False, True):
                for notes in (False, True):
                    parts = build_system_prompt_parts(
                        candidate, opening, s, now=NOW, followup=fu, closed=closed,
                        knowledge=knowledge, frustration_notes=notes,
                    )  # fmt: skip
                    rendered.append(parts.text)
    return rendered


def test_every_template_branch_renders():
    """No branch has a missing variable (StrictUndefined) or an unknown value (`unknown(...)`)."""
    assert all(text.strip() for text in render_all())


# --- the fixed part is the same for every call -------------------------------------------------


def test_fixed_part_does_not_depend_on_the_call():
    """The fixed part is the cached prefix: it must not change with the candidate, the opening,
    the date or the follow-up context. Evals stay green if a per-call value leaks into it."""
    settings = Settings(_env_file=None, timezone="UTC")
    other_opening = Opening(id="o2", role=Role.TUTOR, location="Bilbao", subjects=[Subject.SPANISH])
    other_candidate = Candidate(name="Zed Quux", phone="+1", location="Bilbao", opening_id="o2")
    calls = [
        ("screening", CANDIDATE, OPENING, NOW, None, None),
        ("screening", other_candidate, other_opening, NOW + timedelta(days=40), None, None),
        ("screening", CANDIDATE, OPENING, NOW, FOLLOWUPS[-3], None),
        ("screening", other_candidate, other_opening, NOW, FOLLOWUPS[2], None),
    ]
    booked = Outcome.SCHEDULED
    for closed in (
        ClosedContext("s0", booked, NOW, SLOT),
        ClosedContext("s0", booked, NOW + timedelta(days=9), SLOT_PAST),
        ClosedContext("s0", booked, NOW, None),
        ClosedContext("s0", Outcome.NOT_QUALIFIED, NOW, None),
    ):
        calls.append(("closed", CANDIDATE, OPENING, NOW, None, closed))
        calls.append(
            ("closed", other_candidate, other_opening, NOW + timedelta(days=3), None, closed)
        )
    for knowledge in (False, True):
        for notes in (False, True):
            fixed: dict[tuple, set[str]] = {}
            for shape, candidate, opening, now, fu, closed in calls:
                parts = build_system_prompt_parts(
                    candidate, opening, settings, now=now, followup=fu, closed=closed,
                    knowledge=knowledge, frustration_notes=notes,
                )  # fmt: skip
                # A rejected close is never offered the knowledge tools, so its fixed part is
                # the one without them.
                with_kb = knowledge and not (
                    closed is not None and closed.outcome is not Outcome.SCHEDULED
                )
                fixed.setdefault((shape, with_kb), set()).add(parts.fixed)
                assert parts.text == parts.fixed + "\n\n" + parts.call
            for key, versions in fixed.items():
                assert len(versions) == 1, key
