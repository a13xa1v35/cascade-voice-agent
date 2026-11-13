"""Domain models. Everything here is plain pydantic; persistence lives in store.py."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(UTC)


class ScreeningStatus(StrEnum):
    PENDING = "pending"  # created, nobody connected yet (webrtc)
    DIALING = "dialing"  # Twilio call placed, waiting for the media stream (phone)
    IN_PROGRESS = "in_progress"  # the bot is talking to the candidate
    COMPLETED = "completed"
    FAILED = "failed"


class Outcome(StrEnum):
    SCHEDULED = "scheduled"
    NOT_QUALIFIED = "not_qualified"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    WRONG_PERSON = "wrong_person"
    NO_ANSWER = "no_answer"
    # A call to a candidate whose screening was already decided (booked or rejected): Sofia
    # only informs, nothing is asked. Set by the closed-mode end_call, never by a screening.
    ALREADY_SCREENED = "already_screened"


class Channel(StrEnum):
    """How the candidate talks to Sofia. Persisted as a plain string and also the mode the
    call pipeline is built in: voice (webrtc, phone) or text (typed chat, see textcall.py)."""

    WEBRTC = "webrtc"
    PHONE = "phone"
    TEXT = "text"


class QuestionKey(StrEnum):
    """Stable identifiers for the screening questions."""

    AVAILABILITY_START = "availability_start"
    SUBJECTS = "subjects"
    SCHEDULE = "schedule"
    WORK_AUTHORIZATION = "work_authorization"
    RELEVANT_EXPERIENCE = "relevant_experience"


class Role(StrEnum):
    """The kinds of job an opening can be for. Tutor is the only one for now."""

    TUTOR = "tutor"


class Subject(StrEnum):
    """Canonical subject keys. The model maps whatever the candidate says to these."""

    MATH = "math"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    COMPUTER_SCIENCE = "computer_science"
    ENGLISH = "english"
    SPANISH = "spanish"
    OTHER = "other"


class Level(StrEnum):
    """Teaching levels, with the Spanish school stage in brackets."""

    PRIMARY = "primary"
    SECONDARY = "secondary"  # ESO
    UPPER_SECONDARY = "upper_secondary"  # Bachillerato
    UNIVERSITY = "university"


class Availability(StrEnum):
    """Weekly teaching slots the candidate can cover."""

    WORKDAYS_MORNING = "workdays_morning"
    WORKDAYS_AFTERNOON = "workdays_afternoon"
    SATURDAY_MORNING = "saturday_morning"
    SATURDAY_AFTERNOON = "saturday_afternoon"


class TeachingFormat(StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"
    BOTH = "both"


class Opening(BaseModel):
    """A job opening candidates apply to. It decides what qualifies (needed subjects,
    start window) and where the work is."""

    id: str = Field(default_factory=new_id)
    role: Role
    location: str
    qualify_window_days: int = 14  # a candidate must be able to start within this many days
    subjects: list[Subject] = Field(default_factory=list)  # the subjects the opening needs
    created_at: datetime = Field(default_factory=utcnow)


class Candidate(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    phone: str  # E.164, e.g. +15551234567
    location: str
    opening_id: str
    # Subjects declared when applying; replaced by the confirmed ones when a call ends.
    subjects: list[Subject] = Field(default_factory=list)
    # Language of this candidate's calls; None = the app-wide LANGUAGE setting.
    language: Literal["en", "es"] | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name.strip() else self.name


class Screening(BaseModel):
    id: str = Field(default_factory=new_id)
    candidate_id: str
    channel: Channel
    status: ScreeningStatus = ScreeningStatus.PENDING
    outcome: Outcome | None = None
    call_sid: str | None = None
    slot_id: str | None = None  # set atomically when a slot is booked
    notes: str | None = None
    previous_screening_id: str | None = None  # the unfinished call this one continues
    attempt: int = 1  # 1 for a fresh call, previous attempt + 1 for a follow-up
    created_at: datetime = Field(default_factory=utcnow)


class ScreeningFacts(BaseModel):
    """What the candidate CONFIRMED on a call. Unset (None / empty list) = not asked yet.

    The deterministic qualification rule reads only these.
    """

    start_date: date | None = None
    subjects: list[Subject] = Field(default_factory=list)
    levels: list[Level] = Field(default_factory=list)
    availability: list[Availability] = Field(default_factory=list)
    teaching_format: TeachingFormat | None = None
    work_authorized: bool | None = None
    experience: str | None = None


class SlotMode(StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class OnboardingSlot(BaseModel):
    """An onboarding session. Where it takes place is data (mode + address); the sentence
    that says so is translated by hr_screener.i18n."""

    id: str = Field(default_factory=new_id)
    starts_at: datetime  # timezone-aware
    mode: SlotMode
    address: str | None = None  # in_person only, e.g. "Chamberí, Madrid"
    capacity: int = 5
    booked: int = 0

    @property
    def is_open(self) -> bool:
        return self.booked < self.capacity


class Sentiment(StrEnum):
    """The candidate's overall attitude during the call, as the summary model reads it."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SummaryDraft(BaseModel):
    """What the LLM writes (structured output). Code adds outcome, language and source,
    so the model can never contradict the deterministic qualification result."""

    key_points: list[str] = Field(description="3 to 6 short facts the candidate stated")
    candidate_questions: list[str] = Field(
        description="Questions the candidate asked, especially ones needing a recruiter follow-up"
    )
    next_step: str = Field(description="One sentence: what should happen next with this candidate")
    sentiment: Sentiment = Field(
        description="The candidate's overall attitude during the call, from their own words"
    )
    frustration_signals: list[str] = Field(
        description=(
            "Short quotes of the candidate's own words showing frustration or annoyance with "
            "the call or the assistant; empty if there were none"
        )
    )


class CallSummary(BaseModel):
    """Post-call summary, stored with the screening."""

    outcome: Outcome | None = None
    qualified: bool | None = None
    key_points: list[str] = Field(default_factory=list)
    candidate_questions: list[str] = Field(default_factory=list)
    next_step: str = ""
    # None = not assessed (the fallback summary, or a row from before these fields existed).
    sentiment: Sentiment | None = None
    frustration_signals: list[str] | None = None
    language: str
    source: Literal["llm", "fallback"]
    created_at: datetime = Field(default_factory=utcnow)


class ReferredQuestion(BaseModel):
    """A question the candidate asked that Sofia could not answer, saved for a recruiter to
    follow up after the call. `automatic` is false when Sofia called `refer_to_recruiter`
    and true when the system saved it at finalize (no lost candidate question): then
    `question` is the model's search query, not the candidate's words."""

    id: str = Field(default_factory=new_id)
    screening_id: str
    question: str
    automatic: bool
    language: str  # the call language
    created_at: datetime = Field(default_factory=utcnow)
