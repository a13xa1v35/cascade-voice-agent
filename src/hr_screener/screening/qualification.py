"""Deterministic qualification rule.

The LLM only *collects* facts (typed arguments of the `record_*` tools). Whether the
candidate qualifies is decided here, in plain Python, so it is testable, auditable and
cannot be talked around by a clever caller or a hallucinating model.

Rule, on the facts CONFIRMED on the call (never the subjects declared when applying): authorized
to work AND at least one confirmed subject is one the opening needs AND can start within the
opening's `qualify_window_days` of today. Levels, weekly availability, teaching format and
experience are collected but do not affect qualification; there is still no verdict until each
of them is saved (`missing_questions`), which includes the levels.
"""

from datetime import date, timedelta

from hr_screener.models import Opening, QuestionKey, ScreeningFacts


def missing_questions(facts: ScreeningFacts) -> list[QuestionKey]:
    """The screening questions whose facts are still unset (in question order)."""
    unset = {
        QuestionKey.AVAILABILITY_START: facts.start_date is None,
        QuestionKey.SUBJECTS: not facts.subjects or not facts.levels,
        QuestionKey.SCHEDULE: not facts.availability or facts.teaching_format is None,
        QuestionKey.WORK_AUTHORIZATION: facts.work_authorized is None,
        QuestionKey.RELEVANT_EXPERIENCE: facts.experience is None,
    }
    return [key for key in QuestionKey if unset[key]]


def schedule_half_missing(facts: ScreeningFacts) -> str | None:
    """With exactly one half of the schedule saved, the other half (`availability` or
    `teaching_format`); None when both or neither are saved."""
    if facts.availability and facts.teaching_format is None:
        return "teaching_format"
    if facts.teaching_format is not None and not facts.availability:
        return "availability"
    return None


def subjects_half_missing(facts: ScreeningFacts) -> str | None:
    """With exactly one half of the subjects question saved, the other half (`subjects` or
    `levels`); None when both or neither are saved."""
    if facts.subjects and not facts.levels:
        return "levels"
    if facts.levels and not facts.subjects:
        return "subjects"
    return None


def question_half_missing(facts: ScreeningFacts, key: QuestionKey) -> str | None:
    """The missing half of a two-part question (subjects, schedule); None for any other
    question or when both or neither half is saved."""
    if key is QuestionKey.SUBJECTS:
        return subjects_half_missing(facts)
    if key is QuestionKey.SCHEDULE:
        return schedule_half_missing(facts)
    return None


def still_to_ask(facts: ScreeningFacts) -> list[str]:
    """What is left to ask, in question order: the missing question keys, except that a
    half-answered question (subjects + levels, availability + format) names only its
    missing half, so neither the tools nor the follow-up prompt ever tell the model to ask
    the saved half again."""
    return [question_half_missing(facts, key) or key.value for key in missing_questions(facts)]


def evaluate(facts: ScreeningFacts, opening: Opening, today: date) -> tuple[bool, list[str]]:
    """Return (qualified, reasons). `reasons` explains every failed criterion."""
    reasons: list[str] = []

    if facts.work_authorized is None:
        reasons.append("work authorization not recorded")
    elif not facts.work_authorized:
        reasons.append("not authorized to work")

    if not facts.subjects:
        reasons.append("subjects not recorded")
    elif not set(facts.subjects) & set(opening.subjects):
        reasons.append("no needed subject offered")

    if facts.start_date is None:
        reasons.append("start date not recorded")
    elif facts.start_date > today + timedelta(days=opening.qualify_window_days):
        reasons.append(f"cannot start within {opening.qualify_window_days} days")

    return (not reasons, reasons)
