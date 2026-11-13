"""Translation of what reaches the candidate verbatim: gettext catalogs plus Babel (CLDR).

The prompt, the tool schemas and the tool results are English for every call. Only text the
candidate hears (or the recruiter reads in the summary fallback) is translated here
(`prompt_text.py` holds the English the model reads):

- strings: `src/hr_screener/i18n/locale/<lang>/LC_MESSAGES/messages.po`, compiled to `.mo`. The
  msgids are the English texts, so "en" needs no catalog at all (`NullTranslations`).
  `make messages` extracts the msgids into `messages.pot` and merges them into the `.po`;
  `make compile-messages` writes the `.mo` (a test fails when the `.mo` is stale).
- dates and weekday names: Babel's CLDR data, with explicit patterns that are themselves
  translatable (the spoken styles differ in more than names: "Tuesday, November 10" against
  "martes 10 de noviembre").

Every function takes the language explicitly: nothing here knows "the current language", so
a per-call language is just an argument.
"""

import gettext
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from babel.dates import format_date as babel_format_date
from babel.dates import format_time as babel_format_time
from babel.dates import get_day_names

from hr_screener.models import OnboardingSlot, SlotMode

Lang = Literal["en", "es"]
LANGS: tuple[Lang, ...] = ("en", "es")

LOCALE_DIR = Path(__file__).parent / "locale"
DOMAIN = "messages"


@cache
def translations(lang: Lang) -> gettext.NullTranslations:
    """The catalog of `lang`. "en" is the source language: msgids are returned as they are."""
    if lang == "en":
        return gettext.NullTranslations()
    return gettext.translation(DOMAIN, str(LOCALE_DIR), languages=[lang])


def format_date(day: date, lang: Lang, *, with_year: bool = False) -> str:
    """Date only, spoken style: 'Tuesday, November 10' / 'martes 10 de noviembre'."""
    t = translations(lang)
    if with_year:
        # Translators: CLDR date pattern with year; quote literal words: 'de'.
        pattern = t.pgettext("date pattern with year", "EEEE, MMMM d, y")
    else:
        # Translators: CLDR date pattern; quote literal words: 'de'.
        pattern = t.pgettext("date pattern", "EEEE, MMMM d")
    return babel_format_date(day, format=pattern, locale=lang)


def _format_time(local: datetime, lang: Lang) -> str:
    t = translations(lang)
    # Translators: CLDR time pattern: h is the 12-hour clock, H the 24-hour one, a AM/PM.
    pattern = t.pgettext("time pattern", "h:mm a")
    # Explicit pattern, so the narrow no-break space CLDR puts before AM/PM in its own
    # English time formats (U+202F) never appears: the plain space is ours.
    clock = babel_format_time(local, format=pattern, locale=lang)
    # Translators: a time of day. The plural form follows the hour on a 24-hour clock
    # (Spanish: "a la 1:00" against "a las 17:00"). {time} is the formatted time.
    phrase = t.ngettext("at {time}", "at {time}", local.hour)
    return phrase.format(time=clock)


def format_slot_time(starts_at: datetime, tz: ZoneInfo, lang: Lang) -> str:
    """Slot start in `tz`, spoken: 'Tuesday, November 10 at 9:00 AM' /
    'martes 10 de noviembre a las 9:00'."""
    local = starts_at.astimezone(tz)
    return f"{format_date(local.date(), lang)} {_format_time(local, lang)}"


def render_location(slot: OnboardingSlot, lang: Lang) -> str:
    """Where an onboarding session takes place, as a phrase after 'at'/'en'."""
    t = translations(lang)
    if slot.mode is SlotMode.ONLINE:
        return t.gettext("online, by video call")
    if slot.address:
        return t.gettext("our office in {address}").format(address=slot.address)
    return t.gettext("our office")


def context_unavailable_apology(lang: Lang) -> str:
    """Spoken verbatim (no model turn) when the call history cannot be loaded."""
    return translations(lang).gettext(
        "I'm sorry, we're having a technical problem right now. We'll call you again later. "
        "Goodbye!"
    )


def llm_error_apology(lang: Lang) -> str:
    """Spoken verbatim (no model turn) when Sofia's model keeps failing mid-call."""
    return translations(lang).gettext(
        "Sorry, I'm having a technical problem. We'll call you back shortly."
    )


def search_holding_line(lang: Lang) -> str:
    """Spoken verbatim (no model turn) when a knowledge lookup starts, so the line does not
    go quiet while it runs. A fixed line: a model-written preamble is where reasoning leaks."""
    return translations(lang).gettext("Let me check that.")


def summary_fallback_next_step(lang: Lang, *, already_screened: bool) -> str:
    """The recruiter's next step when no LLM summary is available."""
    t = translations(lang)
    if already_screened:
        return t.gettext(
            "The candidate was already screened and no questions were asked. Read the "
            "transcript and notes: contact them if they asked to reschedule or cancel."
        )
    return t.gettext(
        "Review the recorded facts and the transcript; no automatic summary was available."
    )


def _fold(text: str) -> str:
    """Lowercase and strip accents, so 'MIÉRCOLES' == 'miercoles'."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@cache
def _weekday_names() -> dict[str, int]:
    """Folded weekday name, in any supported language -> Monday=0 (CLDR 'wide' names)."""
    return {
        _fold(name): index
        for lang in LANGS
        for index, name in get_day_names("wide", locale=lang).items()
    }


def weekday_index(name: str) -> int | None:
    """Monday=0 for a weekday name in ANY supported language, ignoring case and accents
    ('lunes', 'Miércoles', 'WEDNESDAY'); None for anything else."""
    return _weekday_names().get(_fold(name))


# --- the recorded facts as words, for the summary fallback (the recruiter reads it) ---


@dataclass(frozen=True)
class FactWords:
    """How the confirmed facts are worded. The prompt's follow-up section and the summary
    fallback render the same facts; this is the part that differs (prompt_text.py has the
    English one the model reads, `fact_words` the translated one the recruiter reads)."""

    date: Callable[[date], str]  # with year
    join: Callable[[list[str]], str]
    subject: Callable[[str], str]  # Subject value -> name
    enum: Callable[[str, str], str]  # (enum name, value) -> label, e.g. ("level", "primary")
    field: Callable[[str], str]  # QuestionKey value -> label
    subjects_value: Callable[[str, str], str]  # (subjects, levels)
    schedule_value: Callable[[str, str], str]  # (availability, format)
    yes: str
    no: str


def join_list(items: list[str], lang: Lang) -> str:
    """['a', 'b', 'c'] -> 'a, b and c' / 'a, b y c' ('física e informática' before an /i/)."""
    if len(items) == 1:
        return items[0]
    t = translations(lang)
    # Translators: the word before the last item of a list.
    conjunction = t.pgettext("list conjunction", "and")
    last = items[-1].lower()
    if last.startswith(("i", "í", "hi")) and not last.startswith("hie"):
        # Translators: the same word before an item that starts with an /i/ sound, where the
        # language changes it (Spanish "y" becomes "e": "física e informática").
        conjunction = t.pgettext("list conjunction before an i sound", "and")
    return ", ".join(items[:-1]) + f" {conjunction} " + items[-1]


@cache
def _subject_names(lang: Lang) -> dict[str, str]:
    t = translations(lang)
    return {
        "math": t.pgettext("subject", "math"),
        "physics": t.pgettext("subject", "physics"),
        "chemistry": t.pgettext("subject", "chemistry"),
        "computer_science": t.pgettext("subject", "computer science"),
        "english": t.pgettext("subject", "English"),
        "spanish": t.pgettext("subject", "Spanish"),
        "other": t.pgettext("subject", "other subjects"),
    }


@cache
def _enum_labels(lang: Lang) -> dict[tuple[str, str], str]:
    t = translations(lang)
    return {
        ("level", "primary"): t.pgettext("level", "primary"),
        ("level", "secondary"): t.pgettext("level", "secondary (ESO)"),
        ("level", "upper_secondary"): t.pgettext("level", "upper secondary (Bachillerato)"),
        ("level", "university"): t.pgettext("level", "university"),
        ("availability", "workdays_morning"): t.pgettext("availability", "weekday mornings"),
        ("availability", "workdays_afternoon"): t.pgettext("availability", "weekday afternoons"),
        ("availability", "saturday_morning"): t.pgettext("availability", "Saturday mornings"),
        ("availability", "saturday_afternoon"): t.pgettext("availability", "Saturday afternoons"),
        ("teaching_format", "in_person"): t.pgettext("teaching format", "in person"),
        ("teaching_format", "online"): t.pgettext("teaching format", "online"),
        ("teaching_format", "both"): t.pgettext("teaching format", "both in person and online"),
    }


@cache
def _field_labels(lang: Lang) -> dict[str, str]:
    t = translations(lang)
    return {
        "availability_start": t.pgettext("fact", "start date"),
        "subjects": t.pgettext("fact", "subjects"),
        "schedule": t.pgettext("fact", "weekly schedule"),
        "work_authorization": t.pgettext("fact", "work authorization"),
        "relevant_experience": t.pgettext("fact", "relevant experience"),
    }


def fact_words(lang: Lang) -> FactWords:
    """The facts worded in `lang` (for the summary fallback)."""
    t = translations(lang)
    subjects = _subject_names(lang)
    labels = _enum_labels(lang)
    fields = _field_labels(lang)
    # Translators: {subjects} and {levels} are already lists of names.
    subjects_value = t.gettext("{subjects}; levels: {levels}")
    # Translators: {availability} is a list of slots, {format} the teaching format.
    schedule_value = t.gettext("{availability}; format: {format}")
    return FactWords(
        date=lambda day: format_date(day, lang, with_year=True),
        join=lambda items: join_list(items, lang),
        subject=lambda value: subjects.get(value, value),
        enum=lambda enum, value: labels[(enum, value)],
        field=lambda key: fields[key],
        subjects_value=lambda s, lv: subjects_value.format(subjects=s, levels=lv),
        schedule_value=lambda a, f: schedule_value.format(availability=a, format=f),
        yes=t.pgettext("answer", "yes"),
        no=t.pgettext("answer", "no"),
    )
