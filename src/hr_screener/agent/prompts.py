"""System prompt for the screening agent.

The text is English for every call and lives in the Jinja templates next to this module
(templates/screening.j2 for a first call or a follow-up, templates/closed.j2 for a booked or
rejected candidate, templates/_shared.j2 for the sections both use). A template reads top to
bottom like the prompt; this module decides which branch applies (what is still to ask, whether
the candidate qualifies, whether the session is past, ...) and passes plain values and
booleans, never prompt text. Candidate-derived text (names, the callback note, summary points,
questions) reaches the templates only as variables.

The one thing that depends on the call language (`Settings.language`) is the "# Language"
section: `LANGUAGE_RULE` tells the model which language to speak. Slot times in a closed-mode
prompt are the values the candidate would hear, so they are worded in the call language
(hr_screener.i18n), like the slots the tools return.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, StrictUndefined, Template

from hr_screener import i18n
from hr_screener.agent.prompt_text import (
    FACT_WORDS,
    LANGUAGE_RULE,
    PROMPT,
    RESULTS,
    country,
    fmt,
    label,
    lang_name,
    list_join,
    refs,
    subject_names,
)
from hr_screener.agent.tools import slot_payload
from hr_screener.config import Settings
from hr_screener.i18n import FactWords, Lang
from hr_screener.models import (
    Candidate,
    Opening,
    Outcome,
    QuestionKey,
    ScreeningFacts,
    Subject,
)
from hr_screener.screening.followup import ClosedContext, EndedHow, FollowUpContext
from hr_screener.screening.qualification import evaluate, missing_questions, still_to_ask

CALENDAR_EXTRA_DAYS = 7  # the calendar covers the qualify window plus this many days

# No autoescape (it is a prompt, not HTML), StrictUndefined (a variable a template needs but
# the code did not pass fails the render), no line statements (headings start with "#").
# trim_blocks + lstrip_blocks: a `{% ... %}` tag on a line of its own leaves no blank line.
_env = Environment(
    loader=PackageLoader("hr_screener.agent", "templates"),
    autoescape=False,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _unknown(what: str, value: object) -> str:
    """Called by the `{% else %}` of a template's branch chains: a value the template has no
    text for is a bug here, not an empty section."""
    raise ValueError(f"no prompt text for {what} = {value!r}")


def _names(prefix: str) -> SimpleNamespace:
    return SimpleNamespace(
        **{k.removeprefix(prefix): v for k, v in refs().items() if k.startswith(prefix)}
    )


# `{{ t.end_call }}` / `{{ p.notes }}` in the templates: the tool and parameter names the model
# sees, so renaming one is a one-line change in prompt_text.TOOLS.
_globals: dict[str, Any] = {"t": _names("t_"), "p": _names("p_"), "unknown": _unknown}
_env.globals.update(_globals)
# Loaded at import so a syntax error fails here, not on the first call. The shared macros are
# only compiled when a template imports them, so load them too.
_env.get_template("_shared.j2")
_SCREENING = _env.get_template("screening.j2")
_CLOSED = _env.get_template("closed.j2")


def _kb_language(settings: Settings) -> str:
    return lang_name(settings.kb_language)


def language_rule(settings: Settings, lang: Lang, *, knowledge: bool = False) -> str:
    """The rule for speaking `lang`, plus the exception for the search query when the knowledge
    tools are offered. Also what `switch_language` returns, so the two cannot drift."""
    rule = fmt(LANGUAGE_RULE[lang])
    if knowledge:
        rule += " " + fmt(
            PROMPT["language_knowledge_exception"], kb_language=_kb_language(settings)
        )
    return rule


def fact_values(facts: ScreeningFacts, words: FactWords = FACT_WORDS) -> dict[QuestionKey, str]:
    """The confirmed facts as text, one entry per question that is fully answered. `words`
    is the wording: English for the model (the default), `i18n.fact_words(lang)` for the
    recruiter."""
    answered = set(QuestionKey) - set(missing_questions(facts))
    values: dict[QuestionKey, str] = {}
    if QuestionKey.AVAILABILITY_START in answered and facts.start_date:
        values[QuestionKey.AVAILABILITY_START] = (
            f"{words.date(facts.start_date)} ({facts.start_date})"
        )
    if QuestionKey.SUBJECTS in answered:
        values[QuestionKey.SUBJECTS] = words.subjects_value(
            words.join([words.subject(s.value) for s in facts.subjects]),
            words.join([words.enum("level", v.value) for v in facts.levels]),
        )
    if QuestionKey.SCHEDULE in answered and facts.teaching_format and facts.availability:
        values[QuestionKey.SCHEDULE] = words.schedule_value(
            words.join([words.enum("availability", v.value) for v in facts.availability]),
            words.enum("teaching_format", facts.teaching_format.value),
        )
    if QuestionKey.WORK_AUTHORIZATION in answered and facts.work_authorized is not None:
        values[QuestionKey.WORK_AUTHORIZATION] = words.yes if facts.work_authorized else words.no
    if QuestionKey.RELEVANT_EXPERIENCE in answered and facts.experience:
        values[QuestionKey.RELEVANT_EXPERIENCE] = facts.experience.strip()
    return values


def _calendar(today: date, opening: Opening) -> list[dict[str, str]]:
    """One entry per day from today through the opening's qualify window + 7 days:
    spoken date and ISO date."""
    return [
        {
            "date": i18n.format_date(day, "en", with_year=True),
            "iso": day.isoformat(),
        }
        for day in (
            today + timedelta(days=offset)
            for offset in range(opening.qualify_window_days + CALENDAR_EXTRA_DAYS + 1)
        )
    ]


@dataclass(frozen=True)
class _Previous:
    """What the "# Previous call" section tells: plain values, no prompt text."""

    when: str
    attempt: int
    ended: EndedHow
    callback_note: str | None
    confirmed: list[tuple[str, str]]  # (field label, value) of every fully answered question
    # The saved half of a half-answered question (subjects + levels, weekly slots + format);
    # empty when there is none.
    half_subjects: str
    half_levels: str
    half_availability: str
    half_format: str
    missing: str  # the questions still to ask, as spoken labels; empty when none is missing
    qualified: bool | None  # the rule's verdict on the carried-over facts; None while incomplete
    next_step_not_qualified: str
    key_points: str
    candidate_questions: str
    referred_questions: list[str]
    stale_start_date: str

    @property
    def has_half(self) -> bool:
        return bool(
            self.half_subjects or self.half_levels or self.half_availability or self.half_format
        )


def _previous(
    followup: FollowUpContext, settings: Settings, opening: Opening, today: date
) -> _Previous:
    facts = followup.facts
    summary = followup.summary
    subjects = levels = availability = fmt_label = ""
    if facts.subjects and not facts.levels:
        subjects = list_join(subject_names([v.value for v in facts.subjects]))
    elif facts.levels and not facts.subjects:
        levels = list_join([label("level", v.value) for v in facts.levels])
    if facts.availability and facts.teaching_format is None:
        availability = list_join([label("availability", v.value) for v in facts.availability])
    elif facts.teaching_format is not None and not facts.availability:
        fmt_label = label("teaching_format", facts.teaching_format.value)
    # The verdict is only known once every question is answered.
    qualified = None if missing_questions(facts) else evaluate(facts, opening, today)[0]
    missing = still_to_ask(facts)
    # A fallback summary's key points are the saved facts again, already listed above;
    # repeating them made Sofia treat the call as settled and offer slots at once (lesson 18).
    key_points = "; ".join(summary.key_points) if summary and summary.source != "fallback" else ""
    return _Previous(
        when=i18n.format_slot_time(followup.previous_at, ZoneInfo(settings.timezone), "en"),
        attempt=followup.attempt,
        ended=followup.ended,
        callback_note=followup.callback_note,
        confirmed=[(FACT_WORDS.field(key.value), v) for key, v in fact_values(facts).items()],
        half_subjects=subjects,
        half_levels=levels,
        half_availability=availability,
        half_format=fmt_label,
        missing=list_join([FACT_WORDS.field(item) for item in missing]) if missing else "",
        qualified=qualified,
        next_step_not_qualified=fmt(RESULTS["next_step_not_qualified"]),
        key_points=key_points,
        candidate_questions="; ".join(summary.candidate_questions) if summary else "",
        referred_questions=[r.question for r in followup.referred_questions],
        stale_start_date=(
            i18n.format_date(followup.stale_start_date, "en", with_year=True)
            if followup.stale_start_date
            else ""
        ),
    )


def _question_tags(followup: FollowUpContext | None, candidate: Candidate) -> list[str]:
    """The questions the call still has to ask, as the names screening.j2 branches on. A
    follow-up lists only what is missing; a half-saved question asks only its missing half
    (`levels` / `subjects_only`, `teaching_format` / `availability`); `subjects_open` is the
    subjects question when the candidate declared none."""
    asked = still_to_ask(followup.facts) if followup else [q.value for q in QuestionKey]
    subjects_only = bool(followup and followup.facts.levels and not followup.facts.subjects)
    tags = []
    for item in asked:
        if item == QuestionKey.SUBJECTS and subjects_only:
            tags.append("subjects_only")
        elif item == QuestionKey.SUBJECTS and not candidate.subjects:
            tags.append("subjects_open")
        else:
            tags.append(item)
    return tags


def _subject_list(subjects: list[Subject]) -> str:
    return list_join(subject_names([s.value for s in subjects])) if subjects else ""


@dataclass(frozen=True)
class SystemPrompt:
    """The system prompt in two parts. `fixed` is identical for every call with the same
    settings, mode and knowledge / notes flags (no candidate, opening or date in it) and comes
    first, so the provider can cache it across calls; `call` is everything that differs per
    call. `text` is what the model reads."""

    fixed: str
    call: str

    @property
    def text(self) -> str:
        return self.fixed + "\n\n" + self.call


def _render_block(template: Template, block: str, values: dict[str, Any]) -> str:
    """Render one `{% block %}` of a template on its own, with only `values` as the context
    (StrictUndefined: a variable the block needs but `values` lacks fails the render)."""
    return "".join(template.blocks[block](template.new_context(values))).strip("\n")


def build_system_prompt_parts(
    candidate: Candidate,
    opening: Opening,
    settings: Settings,
    *,
    now: datetime | None = None,
    followup: FollowUpContext | None = None,
    closed: ClosedContext | None = None,
    knowledge: bool = False,
    frustration_notes: bool = False,
) -> SystemPrompt:
    """The system prompt. `closed` (booked / rejected candidate, see followup.CallMode) swaps
    the whole screening for a short inform-only prompt without the questions. `knowledge`
    is true when the knowledge tools are offered: it adds the knowledge section and the rule
    variants that mention them (no other change to the text). `frustration_notes` is true
    when the call's monitor can send notes: it adds the section that says how to treat them (the
    caller decides, see `pipeline.frustration.notes_available`; nothing here reads settings).
    A booking whose session already started by `now` (default: the real clock) is told as past,
    with no claim about attendance.

    The `fixed` block of the template is rendered from the settings and flags alone."""
    tz = ZoneInfo(settings.timezone)
    today = (now.astimezone(tz) if now else datetime.now(tz)).date()
    if closed is not None:
        # The rejected close is not offered the knowledge tools (tools.knowledge_offered).
        knowledge = knowledge and closed.outcome is Outcome.SCHEDULED
    template = _SCREENING if closed is None else _CLOSED
    fixed_values: dict[str, Any] = {
        "agent": settings.agent_name,
        "agency": settings.agency_name,
        "country": country(settings.country),
        "kb_language": _kb_language(settings),
        "lang_name": lang_name(settings.language),
        "language_rule": language_rule(settings, settings.language, knowledge=knowledge),
        "knowledge": knowledge,
        "frustration_notes": frustration_notes,
    }
    call_values: dict[str, Any] = {
        "name": candidate.name,
        "first_name": candidate.first_name,
        "role": label("role", opening.role.value),
        "location": opening.location,
    }
    if closed is not None:
        if closed.outcome is not Outcome.SCHEDULED:
            call_values["situation"] = "rejected"
        elif closed.slot is None:
            call_values["situation"] = "booked_no_slot"
        else:
            # Rendered in the call language, like the slots the tools return.
            shown = slot_payload(closed.slot, tz, settings.language)
            call_values["when"], call_values["place"] = shown["when"], shown["location"]
            past = closed.session_passed(now or datetime.now(tz))
            call_values["situation"] = "booked_past" if past else "booked"
    else:
        # Interest is asked once per screening: a follow-up whose earlier call reached the
        # questions only checks the moment, and not even that right after a dropped call.
        if followup is None or not followup.interest_confirmed:
            interest = "ask"
        elif followup.is_recent(now or datetime.now(UTC), settings.followup_recent_minutes):
            interest = "recent"
        else:
            interest = "later"
        call_values |= {
            "needed_subjects": _subject_list(opening.subjects),
            "declared_subjects": _subject_list(candidate.subjects),
            "timezone": settings.timezone,
            "followup": _previous(followup, settings, opening, today) if followup else None,
            "interest": interest,
            "questions": _question_tags(followup, candidate),
            "days": _calendar(today, opening),
        }
    return SystemPrompt(
        fixed=_render_block(template, "fixed", fixed_values),
        call=_render_block(template, "call", fixed_values | call_values) + "\n",
    )


def build_system_prompt(
    candidate: Candidate,
    opening: Opening,
    settings: Settings,
    *,
    now: datetime | None = None,
    followup: FollowUpContext | None = None,
    closed: ClosedContext | None = None,
    knowledge: bool = False,
    frustration_notes: bool = False,
) -> str:
    """`build_system_prompt_parts(...).text`: the whole prompt as one string."""
    return build_system_prompt_parts(
        candidate,
        opening,
        settings,
        now=now,
        followup=followup,
        closed=closed,
        knowledge=knowledge,
        frustration_notes=frustration_notes,
    ).text
