from datetime import date, timedelta

from hr_screener.models import (
    Availability,
    Level,
    Opening,
    QuestionKey,
    Role,
    ScreeningFacts,
    Subject,
    TeachingFormat,
)
from hr_screener.screening.qualification import evaluate, missing_questions

TODAY = date(2026, 11, 8)
NEEDED = [Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE]
OPENING = Opening(role=Role.TUTOR, location="Madrid", qualify_window_days=14, subjects=NEEDED)


def facts(
    *,
    authorized: bool = True,
    start: date = TODAY + timedelta(days=3),
    subjects: list[Subject] | None = None,
) -> ScreeningFacts:
    return ScreeningFacts(
        start_date=start,
        subjects=[Subject.MATH] if subjects is None else subjects,
        levels=[Level.SECONDARY],
        availability=[Availability.WORKDAYS_AFTERNOON],
        teaching_format=TeachingFormat.ONLINE,
        work_authorized=authorized,
        experience="tutored for two years",
    )


def run(f: ScreeningFacts, opening: Opening = OPENING):
    return evaluate(f, opening, TODAY)


def test_one_needed_subject_among_others_is_enough():
    assert run(facts(subjects=[Subject.CHEMISTRY, Subject.PHYSICS]))[0]


def test_only_non_needed_subjects_do_not_qualify():
    qualified, reasons = run(facts(subjects=[Subject.CHEMISTRY, Subject.ENGLISH]))
    assert not qualified
    assert reasons == ["no needed subject offered"]


def test_needed_subjects_come_from_the_opening():
    chemistry = OPENING.model_copy(update={"subjects": [Subject.CHEMISTRY]})
    assert run(facts(subjects=[Subject.CHEMISTRY]), chemistry)[0]
    assert not run(facts(subjects=[Subject.MATH]), chemistry)[0]


def test_not_authorized_does_not_qualify():
    qualified, reasons = run(facts(authorized=False))
    assert not qualified
    assert reasons == ["not authorized to work"]


def test_start_window_boundary_is_inclusive():
    assert run(facts(start=TODAY + timedelta(days=14)))[0]
    qualified, reasons = run(facts(start=TODAY + timedelta(days=15)))
    assert not qualified
    assert reasons == ["cannot start within 14 days"]


def test_window_comes_from_the_opening():
    short = OPENING.model_copy(update={"qualify_window_days": 3})
    assert not run(facts(start=TODAY + timedelta(days=5)), short)[0]
    assert run(facts(start=TODAY + timedelta(days=5)))[0]


def test_missing_questions_maps_facts_to_question_keys():
    assert missing_questions(ScreeningFacts()) == list(QuestionKey)
    assert missing_questions(facts()) == []

    def missing(**unset) -> list[QuestionKey]:
        return missing_questions(facts().model_copy(update=unset))

    assert missing(start_date=None) == [QuestionKey.AVAILABILITY_START]
    assert missing(subjects=[]) == [QuestionKey.SUBJECTS]
    assert missing(levels=[]) == [QuestionKey.SUBJECTS]  # subjects need both
    assert missing(availability=[]) == [QuestionKey.SCHEDULE]
    assert missing(teaching_format=None) == [QuestionKey.SCHEDULE]  # schedule needs both
    assert missing(work_authorized=None) == [QuestionKey.WORK_AUTHORIZATION]
    assert missing(experience=None) == [QuestionKey.RELEVANT_EXPERIENCE]
