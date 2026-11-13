"""Persona cards: who the simulated candidate is and what is true about them.

A card is language-neutral (`personas/*.toml`): the canonical facts the screening collects,
plus a speaking style. The simulator turns them into the call language; the checks compare
the facts Sofia saved with the card. Dates are relative specs resolved against the call
timezone's "today", so a card never goes stale:

    today | tomorrow | yesterday | in_<n>_days | in_<n>_weeks | next_<weekday> | YYYY-MM-DD

`next_monday` is the first Monday strictly after today.
"""

import re
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

PERSONA_DIR = Path(__file__).parent / "personas"
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def resolve_date(spec: str, today: date) -> date:
    """A relative date spec as a date (see the module docstring)."""
    spec = spec.strip().lower()
    if spec == "today":
        return today
    if spec == "tomorrow":
        return today + timedelta(days=1)
    if spec == "yesterday":
        return today - timedelta(days=1)
    if m := re.fullmatch(r"in_(\d+)_(days|weeks)", spec):
        n = int(m.group(1)) * (7 if m.group(2) == "weeks" else 1)
        return today + timedelta(days=n)
    if m := re.fullmatch(r"next_([a-z]+)", spec):
        if m.group(1) not in _WEEKDAYS:
            raise ValueError(f"unknown weekday in date spec {spec!r}")
        ahead = (_WEEKDAYS.index(m.group(1)) - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", spec):
        return date.fromisoformat(spec)
    raise ValueError(f"unknown date spec {spec!r}")


_PLACEHOLDER = re.compile(r"\{date:([^}]+)\}")


def render_instruction(text: str, today: date) -> str:
    """Replace `{date:<spec>}` placeholders by a concrete ISO date and its weekday, so a
    scenario can say "you can only start on {date:in_60_days}" without hard-coding a date."""

    def one(m: re.Match[str]) -> str:
        day = resolve_date(m.group(1), today)
        return f"{day.isoformat()} ({day.strftime('%A')})"

    return _PLACEHOLDER.sub(one, text)


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    style: str
    start_date_spec: str
    subjects: tuple[str, ...]
    levels: tuple[str, ...]
    availability: tuple[str, ...]
    teaching_format: str
    work_authorized: bool
    experience: str
    notes: str = ""

    def start_date(self, today: date) -> date:
        return resolve_date(self.start_date_spec, today)

    def expected_facts(self, today: date) -> dict[str, object]:
        """The canonical facts Sofia should end up with, JSON-friendly (sets as sorted lists)."""
        return {
            "start_date": self.start_date(today).isoformat(),
            "subjects": sorted(self.subjects),
            "levels": sorted(self.levels),
            "availability": sorted(self.availability),
            "teaching_format": self.teaching_format,
            "work_authorized": self.work_authorized,
        }

    def card_text(self, today: date) -> str:
        """The card as the simulator prompt shows it (language-neutral, dates resolved)."""
        start = self.start_date(today)
        return "\n".join(
            [
                f"Name: {self.name}",
                f"Speaking style: {self.style}",
                f"Earliest start date: {start.isoformat()} ({start.strftime('%A')})",
                f"Subjects you can teach: {', '.join(self.subjects)}",
                f"Levels you can teach: {', '.join(self.levels)}",
                f"Weekly availability: {', '.join(self.availability)}",
                f"Teaching format: {self.teaching_format}",
                f"Authorized to work in Spain: {'yes' if self.work_authorized else 'no'}",
                f"Relevant experience: {self.experience}",
            ]
        )


def parse_persona(persona_id: str, raw: dict) -> Persona:
    facts = raw["facts"]
    return Persona(
        id=persona_id,
        name=raw["name"],
        style=raw["style"],
        start_date_spec=facts["start_date"],
        subjects=tuple(facts["subjects"]),
        levels=tuple(facts["levels"]),
        availability=tuple(facts["availability"]),
        teaching_format=facts["teaching_format"],
        work_authorized=bool(facts["work_authorized"]),
        experience=facts["experience"],
        notes=raw.get("notes", ""),
    )


def load_persona(persona_id: str, directory: Path = PERSONA_DIR) -> Persona:
    with (directory / f"{persona_id}.toml").open("rb") as f:
        return parse_persona(persona_id, tomllib.load(f))


def load_all(directory: Path = PERSONA_DIR) -> dict[str, Persona]:
    return {p.stem: load_persona(p.stem, directory) for p in sorted(directory.glob("*.toml"))}
