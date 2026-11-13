"""The public demo: input validation for POST /demo/call and the page's options."""

import hmac
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from hr_screener.config import Settings
from hr_screener.models import Subject

LANGUAGES = {"en": "English", "es": "Spanish"}
MIN_FUTURE_SLOTS = 6  # the demo always has at least this many onboarding slots ahead

_E164 = re.compile(r"\+[1-9]\d{7,14}")


def normalize_phone(raw: str) -> str:
    """E.164 from what people type: spaces, dashes, dots and brackets are dropped and a
    leading 00 means +. Raises ValueError unless a country code is present."""
    phone = re.sub(r"[\s\-.()]", "", raw)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not _E164.fullmatch(phone):
        raise ValueError("phone must be in international format, e.g. +34600111222")
    return phone


class DemoAccessIn(BaseModel):
    access_code: str = Field(default="", max_length=200)


class DemoCallIn(DemoAccessIn):
    name: str = Field(min_length=1, max_length=80)
    phone: str
    subjects: list[Subject] = Field(default_factory=list, max_length=len(Subject))
    language: Literal["en", "es"]
    consent: bool

    @field_validator("name")
    @classmethod
    def _stripped(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def _e164(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("consent")
    @classmethod
    def _consented(cls, value: bool) -> bool:
        if not value:
            raise ValueError("consent is required")
        return value


def access_code_valid(settings: Settings, supplied: str) -> bool:
    """True when `supplied` is one of the configured DEMO_ACCESS_CODES. Compares against every
    code in constant time; no codes configured means nobody gets in."""
    codes = [c.strip() for c in settings.demo_access_codes.split(",") if c.strip()]
    supplied_bytes = supplied.strip().encode()
    # a list, not a generator: any() would stop at the first match and leak which code it was
    return any([hmac.compare_digest(supplied_bytes, c.encode()) for c in codes])  # noqa: C419


def demo_options(settings: Settings) -> dict[str, object]:
    return {
        "subjects": [s.value for s in Subject],
        "languages": [{"code": code, "label": label} for code, label in LANGUAGES.items()],
        "call_time_limit_minutes": max(1, settings.call_time_limit_secs // 60),
        "agency_name": settings.agency_name,
        "agent_name": settings.agent_name,
        "author_name": settings.demo_author_name,
        "github_url": settings.demo_github_url,
        "linkedin_url": settings.demo_linkedin_url,
    }
