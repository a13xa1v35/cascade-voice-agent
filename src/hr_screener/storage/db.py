"""SQL schema and engine factory (SQLAlchemy 2.0 Core, async).

The database is the system of record; Redis only holds the per-call event timeline
(telemetry, with a TTL).
Schema changes go through Alembic (`make migrate`); the app never creates tables itself.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

metadata = sa.MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class UTCDateTime(sa.TypeDecorator[datetime]):
    """Timezone-aware datetimes that survive SQLite, which drops tzinfo.

    Values are converted to UTC on the way in (naive ones are assumed to be UTC) and come
    back as UTC-aware datetimes, whatever the backend does with the zone.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


openings = sa.Table(
    "openings",
    metadata,
    sa.Column("id", sa.String(12), primary_key=True),
    sa.Column("role", sa.String, nullable=False),
    sa.Column("location", sa.String, nullable=False),
    sa.Column("qualify_window_days", sa.Integer, nullable=False),
    sa.Column("created_at", UTCDateTime, nullable=False),
)

# The subjects an opening needs: a candidate qualifies by confirming at least one of them.
opening_subjects = sa.Table(
    "opening_subjects",
    metadata,
    sa.Column("opening_id", sa.ForeignKey("openings.id"), primary_key=True),
    sa.Column("subject", sa.String, primary_key=True),
)

candidates = sa.Table(
    "candidates",
    metadata,
    sa.Column("id", sa.String(12), primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("phone", sa.String, nullable=False),
    sa.Column("location", sa.String, nullable=False),
    sa.Column("opening_id", sa.ForeignKey("openings.id"), nullable=False),
    sa.Column("language", sa.String, nullable=True),
    sa.Column("created_at", UTCDateTime, nullable=False),
)

# The subjects the candidate DECLARED when applying (updated to the confirmed ones when a
# call ends).
candidate_subjects = sa.Table(
    "candidate_subjects",
    metadata,
    sa.Column("candidate_id", sa.ForeignKey("candidates.id"), primary_key=True),
    sa.Column("subject", sa.String, primary_key=True),
)

screenings = sa.Table(
    "screenings",
    metadata,
    sa.Column("id", sa.String(12), primary_key=True),
    sa.Column("candidate_id", sa.ForeignKey("candidates.id"), nullable=False),
    sa.Column("channel", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("outcome", sa.String, nullable=True),
    sa.Column("call_sid", sa.String, nullable=True),
    sa.Column("notes", sa.Text, nullable=True),
    sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
    sa.Column("previous_screening_id", sa.ForeignKey("screenings.id"), nullable=True),
    sa.Column("created_at", UTCDateTime, nullable=False),
    sa.Index("ix_screenings_candidate_id_created_at", "candidate_id", "created_at"),
)

slots = sa.Table(
    "slots",
    metadata,
    sa.Column("id", sa.String(12), primary_key=True),
    sa.Column("starts_at", UTCDateTime, nullable=False, index=True),
    sa.Column("mode", sa.String, nullable=False),
    sa.Column("address", sa.String, nullable=True),
    sa.Column("capacity", sa.Integer, nullable=False),
    sa.Column("booked", sa.Integer, nullable=False, server_default="0"),
    sa.CheckConstraint("booked >= 0 AND booked <= capacity", name="booked_within_capacity"),
)

# One seat per screening (the primary key). The unique key is the backstop behind
# ScreeningStore.book_slot; `screenings.slot_id` on the domain model is derived from here.
bookings = sa.Table(
    "bookings",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("slot_id", sa.ForeignKey("slots.id"), nullable=False, index=True),
    sa.Column("created_at", UTCDateTime, nullable=False),
)

# What the candidate CONFIRMED on the call. The scalar facts live in one row per screening
# (all nullable: unset = not asked yet); the list facts have a linking table each, one row
# per confirmed value. The qualification rule reads only these.
screening_facts = sa.Table(
    "screening_facts",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("start_date", sa.Date, nullable=True),
    sa.Column("teaching_format", sa.String, nullable=True),
    sa.Column("work_authorized", sa.Boolean, nullable=True),
    sa.Column("experience", sa.Text, nullable=True),
    sa.Column("updated_at", UTCDateTime, nullable=False),
)

screening_subjects = sa.Table(
    "screening_subjects",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("subject", sa.String, primary_key=True),
)

screening_levels = sa.Table(
    "screening_levels",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("level", sa.String, primary_key=True),
)

screening_availability = sa.Table(
    "screening_availability",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("availability", sa.String, primary_key=True),
)

transcript_turns = sa.Table(
    "transcript_turns",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("role", sa.String, nullable=False),
    sa.Column("text", sa.Text, nullable=False),
)

summaries = sa.Table(
    "summaries",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("outcome", sa.String, nullable=True),
    sa.Column("qualified", sa.Boolean, nullable=True),
    sa.Column("key_points", sa.JSON, nullable=False),
    sa.Column("candidate_questions", sa.JSON, nullable=False),
    sa.Column("next_step", sa.Text, nullable=False),
    sa.Column("sentiment", sa.String, nullable=True),
    sa.Column("frustration_signals", sa.JSON, nullable=True),
    sa.Column("language", sa.String, nullable=False),
    sa.Column("source", sa.String, nullable=False),
    sa.Column("created_at", UTCDateTime, nullable=False),
)

# Tool calls of a call, written when it ends (telemetry kept with the record).
tool_calls = sa.Table(
    "tool_calls",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("t", sa.Float, nullable=False),  # seconds into the call
    sa.Column("name", sa.String, nullable=False),
    sa.Column("args", sa.JSON, nullable=False),
    sa.Column("result", sa.JSON, nullable=True),
    sa.Column("ok", sa.Boolean, nullable=False),
    sa.Column("error", sa.Text, nullable=True),
)

# The scalar scorecard of a call (docs/metrics.md), one typed row per screening, written when
# the call ends. Nullable where the scorecard field is optional (no timeline = partial).
call_metrics = sa.Table(
    "call_metrics",
    metadata,
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), primary_key=True),
    sa.Column("computed_at", UTCDateTime, nullable=False),
    sa.Column("partial", sa.Boolean, nullable=False),
    sa.Column("event_count", sa.Integer, nullable=False),
    sa.Column("duration_secs", sa.Float, nullable=True),
    sa.Column("reply_p50", sa.Float, nullable=True),
    sa.Column("reply_p95", sa.Float, nullable=True),
    sa.Column("reply_max", sa.Float, nullable=True),
    sa.Column("tool_turn_p50", sa.Float, nullable=True),
    sa.Column("first_greeting_secs", sa.Float, nullable=True),
    sa.Column("llm_ttfb_p50", sa.Float, nullable=True),
    sa.Column("llm_ttfb_p95", sa.Float, nullable=True),
    sa.Column("user_turns", sa.Integer, nullable=True),
    sa.Column("false_endpoints", sa.Integer, nullable=True),
    sa.Column("barge_ins", sa.Integer, nullable=True),
    sa.Column("silence_fallbacks", sa.Integer, nullable=True),
    sa.Column("unsafe_hangup", sa.Boolean, nullable=True),
    sa.Column("hangup_wait_secs", sa.Float, nullable=True),
    sa.Column("facts_complete", sa.Boolean, nullable=False),
    sa.Column("tool_errors", sa.Integer, nullable=True),
    sa.Column("tool_order_valid", sa.Boolean, nullable=True),
    sa.Column("booked_only_if_qualified", sa.Boolean, nullable=True),
    sa.Column("goodbye_spoken", sa.Boolean, nullable=True),
    sa.Column("end_reason", sa.String, nullable=True),
    sa.Column("llm_calls", sa.Integer, nullable=True),
    sa.Column("prompt_tokens", sa.Integer, nullable=True),
    sa.Column("completion_tokens", sa.Integer, nullable=True),
    sa.Column("cache_read_tokens", sa.Integer, nullable=True),
    sa.Column("reasoning_tokens", sa.Integer, nullable=True),
    sa.Column("wasted_llm_calls", sa.Integer, nullable=True),
    sa.Column("llm_errors", sa.Integer, nullable=True),
    sa.Column("llm_retries", sa.Integer, nullable=True),
    sa.Column("tts_chars", sa.Integer, nullable=True),
    # Knowledge base (README): NULL for a partial row.
    sa.Column("kb_searches", sa.Integer, nullable=True),
    sa.Column("kb_no_match", sa.Integer, nullable=True),
    sa.Column("kb_unavailable", sa.Integer, nullable=True),
    sa.Column("kb_search_p50_ms", sa.Float, nullable=True),
    sa.Column("kb_search_max_ms", sa.Float, nullable=True),
    sa.Column("kb_late_results", sa.Integer, nullable=True),
    sa.Column("questions_referred", sa.Integer, nullable=True),
    # In-call frustration check: NULL when the check did not run in the call.
    sa.Column("frustration_checks", sa.Integer, nullable=True),
    sa.Column("frustration_max", sa.Float, nullable=True),
    sa.Column("frustration_frustrated_checks", sa.Integer, nullable=True),
    sa.Column("frustration_notes", sa.Integer, nullable=True),
)

# Questions Sofia could not answer, saved for a recruiter to follow up (README). `automatic`
# is false when Sofia called refer_to_recruiter, true when the system saved it at finalize.
referred_questions = sa.Table(
    "referred_questions",
    metadata,
    sa.Column("id", sa.String(12), primary_key=True),
    sa.Column("screening_id", sa.ForeignKey("screenings.id"), nullable=False),
    sa.Column("question", sa.Text, nullable=False),
    sa.Column("automatic", sa.Boolean, nullable=False),
    sa.Column("language", sa.String, nullable=False),
    sa.Column("created_at", UTCDateTime, nullable=False),
    sa.Index("ix_referred_questions_screening_id", "screening_id"),
)

# FK-safe deletion order (children first).
TABLES_CHILDREN_FIRST = (
    referred_questions,
    call_metrics,
    tool_calls,
    summaries,
    transcript_turns,
    screening_availability,
    screening_levels,
    screening_subjects,
    screening_facts,
    bookings,
    screenings,
    slots,
    candidate_subjects,
    candidates,
    opening_subjects,
    openings,
)


def _sqlite_file(url: sa.URL) -> str | None:
    """The database file of a SQLite URL; None for other backends and in-memory databases."""
    if not url.drivername.startswith("sqlite"):
        return None
    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return None
    return database


def make_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """Async engine for `url`. Extra kwargs go to `create_async_engine` (tests pass
    `poolclass=StaticPool` for an in-memory database).

    SQLite gets the settings it needs to behave like a database that serializes writers:
    foreign keys on, WAL + busy_timeout for files, and `BEGIN IMMEDIATE` for transactions
    opened through `writer(engine)`, so a write takes the write lock up front (a deferred
    BEGIN would fail with "database is locked" when two readers try to upgrade at once).
    Reads get a plain deferred BEGIN and, under WAL, never wait for writers. Other dialects
    are left untouched.
    """
    parsed = make_url(url)
    path = _sqlite_file(parsed)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        _configure_sqlite(engine, is_file=path is not None)
    return engine


_WRITE_OPTION = "hr_screener_write"


def writer(engine: AsyncEngine) -> AsyncEngine:
    """A view of `engine` (same pool) whose transactions are writes: `BEGIN IMMEDIATE` on
    SQLite, a no-op flag elsewhere."""
    return engine.execution_options(**{_WRITE_OPTION: True})


def _configure_sqlite(engine: AsyncEngine, *, is_file: bool) -> None:
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "connect")
    def on_connect(dbapi_conn: Any, _record: Any) -> None:
        # Take transaction control away from the driver; the "begin" hook below emits BEGIN.
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if is_file:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    @event.listens_for(sync_engine, "begin")
    def on_begin(conn: Any) -> None:
        write = conn.get_execution_options().get(_WRITE_OPTION, False)
        conn.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
