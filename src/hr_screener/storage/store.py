"""Async repository: SQL is the system of record, Redis holds per-call telemetry.

SQL tables (schema in db.py, migrations in migrations/):

    openings               a job opening: role, location, qualify window
    opening_subjects       PK (opening_id, subject): the subjects the opening needs
    candidates             one row per candidate, applying to one opening
    candidate_subjects     PK (candidate_id, subject): subjects declared when applying
                           (replaced by the confirmed ones when a call ends)
    screenings             one row per call (status, outcome, attempt, previous_screening_id,
                           ...); `Screening.slot_id` is derived from `bookings`
    screening_facts        one row per screening: start date, format, work authorization,
                           experience (all nullable) of what the candidate CONFIRMED
    screening_subjects     PK (screening_id, subject)      confirmed subjects
    screening_levels       PK (screening_id, level)        confirmed levels
    screening_availability PK (screening_id, availability) confirmed weekly slots
    transcript_turns       PK (screening_id, seq): role + text per conversation turn
    tool_calls             PK (screening_id, seq): the tool calls of the call, at call end
    call_metrics           one typed scorecard row per screening, at call end
    referred_questions     questions Sofia could not answer, saved for a recruiter
    summaries              one post-call summary per screening
    slots                  onboarding sessions with capacity and a booked counter
    bookings               one seat per screening (PK screening_id) on a slot

Redis keeps the one thing that is telemetry, not a record (the client must use
`decode_responses=True`); it expires `events_ttl_days` after the last flush (see
observability.CallRecorder), after which the scorecard comes from call_metrics + tool_calls:

    screening:{id}:events         list   raw call timeline, JSON per event (CallRecorder)

Booking is the only operation with a real race (two calls offering the last seat). It runs
in one transaction around `UPDATE slots SET booked = booked + 1 WHERE booked < capacity`, so
the capacity check and the increment are a single atomic statement; the primary key on
bookings.screening_id is the backstop against double-booking a screening. The status
compare-and-set is likewise one `UPDATE ... WHERE status = :expected`. On SQLite, writers are
serialized with `BEGIN IMMEDIATE` on write transactions (see db.writer); reads stay deferred.
"""

import json
from collections.abc import Sequence
from datetime import date, datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from hr_screener.models import (
    Availability,
    CallSummary,
    Candidate,
    Channel,
    Level,
    OnboardingSlot,
    Opening,
    Outcome,
    ReferredQuestion,
    Screening,
    ScreeningFacts,
    ScreeningStatus,
    Subject,
    TeachingFormat,
    utcnow,
)
from hr_screener.observability.metrics import (
    Scorecard,
    ToolCall,
    compute_scorecard,
    metrics_row,
    scorecard_from_stored,
    tool_call_rows,
    tool_calls_from_rows,
)
from hr_screener.storage.db import (
    TABLES_CHILDREN_FIRST,
    bookings,
    call_metrics,
    candidate_subjects,
    candidates,
    opening_subjects,
    openings,
    referred_questions,
    screening_availability,
    screening_facts,
    screening_levels,
    screening_subjects,
    screenings,
    slots,
    summaries,
    tool_calls,
    transcript_turns,
    writer,
)


class BookingResult(StrEnum):
    BOOKED = "booked"
    ALREADY_BOOKED = "already_booked"
    FULL = "full"
    NOT_FOUND = "not_found"
    HAS_OTHER_SLOT = "has_other_slot"


# Columns update_screening may write. Everything else (id, candidate_id, created_at) is
# immutable; slot_id is not a column (it comes from bookings).
_UPDATABLE_SCREENING_FIELDS = frozenset(
    c.name for c in screenings.c if c.name not in {"id", "candidate_id", "created_at"}
)

_SCREENING_SELECT = sa.select(*screenings.c, bookings.c.slot_id).select_from(
    screenings.outerjoin(bookings, bookings.c.screening_id == screenings.c.id)
)


def events_key(screening_id: str) -> str:
    """The Redis list holding a call's raw timeline (the only key format in Redis)."""
    return f"screening:{screening_id}:events"


def _screening(row: sa.Row[Any]) -> Screening:
    return Screening.model_validate(row._mapping)


class ScreeningStore:
    def __init__(self, engine: AsyncEngine, redis: Redis) -> None:
        self.engine = engine
        # Every write transaction goes through `_writes` (BEGIN IMMEDIATE on SQLite); reads
        # use `engine.connect()` and stay deferred.
        self._writes = writer(engine)
        # Typed as Any on purpose: redis-py's stubs return broad unions (bytes | str, and
        # awaitable-or-value for the sync/async split) that make every call site noisy.
        # The client must be created with decode_responses=True.
        self.redis: Any = redis

    async def ping_db(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        return True

    async def ping_redis(self) -> bool:
        return bool(await self.redis.ping())

    async def ping(self) -> bool:
        """Database and Redis both reachable (raises if either is not)."""
        return await self.ping_db() and await self.ping_redis()

    async def reset_all(self) -> None:
        """Delete every row from every table, children first. For the seed script."""
        async with self._writes.begin() as conn:
            for table in TABLES_CHILDREN_FIRST:
                await conn.execute(sa.delete(table))

    # --- openings ---

    async def create_opening(self, opening: Opening) -> Opening:
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.insert(openings).values(**opening.model_dump(exclude={"subjects"}))
            )
            await _insert_values(
                conn, opening_subjects, "opening_id", opening.id, "subject", opening.subjects
            )
        return opening.model_copy(update={"subjects": _distinct_in_enum_order(opening.subjects)})

    async def get_opening(self, opening_id: str) -> Opening | None:
        found = await self._load_openings(openings.c.id == opening_id)
        return found[0] if found else None

    async def list_openings(self) -> list[Opening]:
        """Every opening with the subjects it needs, oldest first."""
        return await self._load_openings()

    async def opening_for_screening(self, screening_id: str) -> Opening | None:
        """The opening the screening's candidate applied to."""
        query = (
            sa.select(candidates.c.opening_id)
            .select_from(screenings.join(candidates, candidates.c.id == screenings.c.candidate_id))
            .where(screenings.c.id == screening_id)
        )  # fmt: skip
        async with self.engine.connect() as conn:
            opening_id = (await conn.execute(query)).scalar_one_or_none()
        return await self.get_opening(opening_id) if opening_id else None

    async def _load_openings(self, *where: sa.ColumnElement[bool]) -> list[Opening]:
        query = sa.select(openings).where(*where).order_by(openings.c.created_at, openings.c.id)
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            ids = [r.id for r in rows]
            needed = await _values_by_owner(conn, opening_subjects, "opening_id", "subject", ids)
        return [
            Opening.model_validate(
                {**r._mapping, "subjects": _in_enum_order(Subject, needed.get(r.id, []))}
            )
            for r in rows
        ]

    # --- candidates ---

    async def create_candidate(self, candidate: Candidate) -> Candidate:
        """Insert the candidate and the subjects they declared when applying."""
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.insert(candidates).values(**candidate.model_dump(exclude={"subjects"}))
            )
            await _insert_values(
                conn,
                candidate_subjects,
                "candidate_id",
                candidate.id,
                "subject",
                candidate.subjects,
            )
        return candidate.model_copy(
            update={"subjects": _distinct_in_enum_order(candidate.subjects)}
        )

    async def get_candidate(self, candidate_id: str) -> Candidate | None:
        found = await self._load_candidates(candidates.c.id == candidate_id)
        return found[0] if found else None

    async def most_recent_candidate(self) -> Candidate | None:
        found = await self._load_candidates(newest_first=True, limit=1)
        return found[0] if found else None

    async def set_candidate_subjects(self, candidate_id: str, subjects: Sequence[Subject]) -> None:
        """Replace the candidate's subjects (declared -> confirmed on a call)."""
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.delete(candidate_subjects).where(
                    candidate_subjects.c.candidate_id == candidate_id
                )
            )
            await _insert_values(
                conn, candidate_subjects, "candidate_id", candidate_id, "subject", subjects
            )

    async def _load_candidates(
        self, *where: sa.ColumnElement[bool], newest_first: bool = False, limit: int | None = None
    ) -> list[Candidate]:
        query = sa.select(candidates).where(*where)
        if newest_first:
            query = query.order_by(candidates.c.created_at.desc(), candidates.c.id.desc())
        if limit:
            query = query.limit(limit)
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            declared = await _values_by_owner(
                conn, candidate_subjects, "candidate_id", "subject", [r.id for r in rows]
            )
        return [
            Candidate.model_validate(
                {**r._mapping, "subjects": _in_enum_order(Subject, declared.get(r.id, []))}
            )
            for r in rows
        ]

    # --- screenings ---

    async def create_screening(self, screening: Screening) -> Screening:
        values = screening.model_dump(exclude={"slot_id"})
        async with self._writes.begin() as conn:
            await conn.execute(sa.insert(screenings).values(**values))
        return screening

    async def list_screenings(self, candidate_id: str) -> list[Screening]:
        """The candidate's screenings, newest first."""
        query = (
            _SCREENING_SELECT.where(screenings.c.candidate_id == candidate_id)
            .order_by(screenings.c.created_at.desc(), screenings.c.id.desc())
        )  # fmt: skip
        async with self.engine.connect() as conn:
            return [_screening(r) for r in await conn.execute(query)]

    async def count_screenings_since(self, channel: Channel, since: datetime) -> int:
        """How many screenings of this channel were created at/after `since`."""
        query = sa.select(sa.func.count()).where(
            screenings.c.channel == channel.value, screenings.c.created_at >= since
        )
        async with self.engine.connect() as conn:
            return int((await conn.execute(query)).scalar_one())

    async def latest_screening(self, candidate_id: str) -> Screening | None:
        found = await self.list_screenings(candidate_id)
        return found[0] if found else None

    async def list_screening_ids(self) -> list[str]:
        """Every screening id in this database (for the seed's reset)."""
        async with self.engine.connect() as conn:
            return [r[0] for r in await conn.execute(sa.select(screenings.c.id))]

    async def get_screening(self, screening_id: str) -> Screening | None:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(_SCREENING_SELECT.where(screenings.c.id == screening_id))
            ).first()
        return _screening(row) if row else None

    async def update_screening(self, screening_id: str, **fields: str | None) -> None:
        """Set the given fields; passing None leaves the field untouched. Only the
        screening's own mutable columns are accepted."""
        unknown = fields.keys() - _UPDATABLE_SCREENING_FIELDS
        if unknown:
            raise ValueError(f"cannot update screening field(s): {', '.join(sorted(unknown))}")
        values = {k: v for k, v in fields.items() if v is not None}
        if values:
            async with self._writes.begin() as conn:
                await conn.execute(
                    sa.update(screenings).where(screenings.c.id == screening_id).values(**values)
                )

    async def transition_status(
        self, screening_id: str, expected: ScreeningStatus, new: ScreeningStatus
    ) -> bool:
        """Atomically move status `expected` -> `new`. False if it was not `expected`."""
        stmt = (
            sa.update(screenings)
            .where(screenings.c.id == screening_id, screenings.c.status == expected.value)
            .values(status=new.value)
        )
        async with self._writes.begin() as conn:
            result = await conn.execute(stmt)
        return result.rowcount == 1

    async def finish_screening(
        self, screening_id: str, status: ScreeningStatus, outcome: Outcome | None, notes: str | None
    ) -> None:
        await self.update_screening(
            screening_id,
            status=status.value,
            outcome=outcome.value if outcome else None,
            notes=notes,
        )

    # --- facts (what the candidate confirmed on the call) ---

    async def get_facts(self, screening_id: str) -> ScreeningFacts:
        """The screening's facts; nothing recorded yet = an empty ScreeningFacts."""
        query = sa.select(screening_facts).where(screening_facts.c.screening_id == screening_id)
        async with self.engine.connect() as conn:
            row = (await conn.execute(query)).first()
            ids = [screening_id]
            subjects_ = await _values_by_owner(
                conn, screening_subjects, "screening_id", "subject", ids
            )
            levels_ = await _values_by_owner(conn, screening_levels, "screening_id", "level", ids)
            slots_ = await _values_by_owner(
                conn, screening_availability, "screening_id", "availability", ids
            )
        return ScreeningFacts(
            start_date=row.start_date if row else None,
            teaching_format=TeachingFormat(row.teaching_format)
            if row and row.teaching_format
            else None,
            work_authorized=row.work_authorized if row else None,
            experience=row.experience if row else None,
            subjects=_in_enum_order(Subject, subjects_.get(screening_id, [])),
            levels=_in_enum_order(Level, levels_.get(screening_id, [])),
            availability=_in_enum_order(Availability, slots_.get(screening_id, [])),
        )

    async def set_start_date(self, screening_id: str, start_date: date) -> None:
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id, start_date=start_date)

    async def clear_start_date(self, screening_id: str) -> None:
        """Forget the start date (it went stale). `_upsert_facts` writes None as NULL."""
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id, start_date=None)

    async def set_subjects(self, screening_id: str, subjects: Sequence[Subject]) -> None:
        """Replace the confirmed subjects (the levels are saved separately)."""
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id)
            await _replace_values(conn, screening_subjects, screening_id, "subject", subjects)

    async def set_levels(self, screening_id: str, levels: Sequence[Level]) -> None:
        """Replace the confirmed teaching levels (the subjects are saved separately)."""
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id)
            await _replace_values(conn, screening_levels, screening_id, "level", levels)

    async def set_availability(
        self, screening_id: str, availability: Sequence[Availability]
    ) -> None:
        """Replace the confirmed weekly slots (the teaching format is saved separately)."""
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id)
            await _replace_values(
                conn, screening_availability, screening_id, "availability", availability
            )

    async def set_teaching_format(self, screening_id: str, teaching_format: TeachingFormat) -> None:
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id, teaching_format=teaching_format.value)

    async def set_work_authorized(self, screening_id: str, authorized: bool) -> None:
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id, work_authorized=authorized)

    async def set_experience(self, screening_id: str, experience: str) -> None:
        async with self._writes.begin() as conn:
            await _upsert_facts(conn, screening_id, experience=experience)

    async def copy_facts(self, from_screening_id: str, to_screening_id: str) -> None:
        """Copy the facts row and its three list tables to another screening (follow-ups)."""
        facts = await self.get_facts(from_screening_id)
        async with self._writes.begin() as conn:
            await _upsert_facts(
                conn,
                to_screening_id,
                start_date=facts.start_date,
                teaching_format=facts.teaching_format.value if facts.teaching_format else None,
                work_authorized=facts.work_authorized,
                experience=facts.experience,
            )
            await _replace_values(
                conn, screening_subjects, to_screening_id, "subject", facts.subjects
            )
            await _replace_values(conn, screening_levels, to_screening_id, "level", facts.levels)
            await _replace_values(
                conn, screening_availability, to_screening_id, "availability", facts.availability
            )

    # --- transcript ---

    async def save_transcript(self, screening_id: str, turns: list[dict[str, str]]) -> None:
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.delete(transcript_turns).where(transcript_turns.c.screening_id == screening_id)
            )
            if turns:
                await conn.execute(
                    sa.insert(transcript_turns),
                    [
                        {
                            "screening_id": screening_id,
                            "seq": i,
                            "role": t["role"],
                            "text": t["text"],
                        }
                        for i, t in enumerate(turns)
                    ],
                )

    async def get_transcript(self, screening_id: str) -> list[dict[str, str]]:
        query = (
            sa.select(transcript_turns.c.role, transcript_turns.c.text)
            .where(transcript_turns.c.screening_id == screening_id)
            .order_by(transcript_turns.c.seq)
        )
        async with self.engine.connect() as conn:
            return [{"role": r.role, "text": r.text} for r in await conn.execute(query)]

    # --- referred questions ---

    async def create_referred_question(self, question: ReferredQuestion) -> ReferredQuestion:
        values = question.model_dump(mode="json", exclude={"created_at"})
        values["created_at"] = question.created_at
        async with self._writes.begin() as conn:
            await conn.execute(sa.insert(referred_questions).values(**values))
        return question

    async def list_referred_questions(self, *, screening_id: str) -> list[ReferredQuestion]:
        """The questions referred to a recruiter in one screening, oldest first."""
        query = (
            sa.select(referred_questions)
            .where(referred_questions.c.screening_id == screening_id)
            .order_by(referred_questions.c.created_at, referred_questions.c.id)
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [ReferredQuestion.model_validate(r._mapping) for r in rows]

    # --- call events (Redis) & metrics ---

    async def get_events(self, screening_id: str) -> list[dict[str, Any]]:
        raw = await self.redis.lrange(events_key(screening_id), 0, -1)
        return [json.loads(e) for e in raw]

    async def save_tool_calls(self, screening_id: str, calls: Sequence[ToolCall]) -> None:
        """Replace the call's stored tool calls with those of `calls` that ran."""
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.delete(tool_calls).where(tool_calls.c.screening_id == screening_id)
            )
            if rows := tool_call_rows(calls):
                await conn.execute(
                    sa.insert(tool_calls), [{"screening_id": screening_id, **r} for r in rows]
                )

    async def get_tool_calls(self, screening_id: str) -> list[ToolCall]:
        query = (
            sa.select(tool_calls)
            .where(tool_calls.c.screening_id == screening_id)
            .order_by(tool_calls.c.seq)
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return tool_calls_from_rows([r._mapping for r in rows])

    async def save_call_metrics(self, screening_id: str, card: Scorecard) -> None:
        """Replace the call's metrics row with the scalar fields of `card`."""
        values = {"screening_id": screening_id, **metrics_row(card)}
        async with self._writes.begin() as conn:
            await conn.execute(
                sa.delete(call_metrics).where(call_metrics.c.screening_id == screening_id)
            )
            await conn.execute(sa.insert(call_metrics).values(**values))

    async def get_call_metrics(self, screening_id: str) -> Scorecard | None:
        """The scorecard rebuilt from call_metrics + tool_calls: no exchanges (the timeline
        is gone), flagged `exchanges_expired`. None if nothing was stored."""
        screening = await self.get_screening(screening_id)
        query = sa.select(call_metrics).where(call_metrics.c.screening_id == screening_id)
        async with self.engine.connect() as conn:
            row = (await conn.execute(query)).first()
        if screening is None or row is None:
            return None
        return scorecard_from_stored(
            screening, row._mapping, await self.get_tool_calls(screening_id)
        )

    async def load_scorecard(self, screening_id: str) -> dict[str, Any] | None:
        """The call's scorecard. Events still in Redis: recomputed in full, exchanges
        included. Expired: what call_metrics + tool_calls hold (`exchanges_expired`). Neither
        (an unfinished call): the task section only, `partial`. None if the screening does not
        exist."""
        screening = await self.get_screening(screening_id)
        if screening is None:
            return None
        if events := await self.get_events(screening_id):
            facts = await self.get_facts(screening_id)
            return compute_scorecard(events, screening, facts).model_dump(mode="json")
        if stored := await self.get_call_metrics(screening_id):
            return stored.model_dump(mode="json")
        facts = await self.get_facts(screening_id)
        return compute_scorecard([], screening, facts).model_dump(mode="json")

    async def save_summary(self, screening_id: str, summary: CallSummary) -> None:
        values = summary.model_dump(mode="json", exclude={"created_at"})
        values["created_at"] = summary.created_at
        async with self._writes.begin() as conn:
            await conn.execute(sa.delete(summaries).where(summaries.c.screening_id == screening_id))
            await conn.execute(sa.insert(summaries).values(screening_id=screening_id, **values))

    async def get_summary(self, screening_id: str) -> CallSummary | None:
        query = sa.select(summaries).where(summaries.c.screening_id == screening_id)
        async with self.engine.connect() as conn:
            row = (await conn.execute(query)).first()
        return CallSummary.model_validate(row._mapping) if row else None

    async def latest_screening_id(self) -> str | None:
        """Most recently created screening."""
        query = sa.select(screenings.c.id).order_by(screenings.c.created_at.desc()).limit(1)
        async with self.engine.connect() as conn:
            return (await conn.execute(query)).scalar_one_or_none()

    # --- onboarding slots ---

    async def create_slot(self, slot: OnboardingSlot) -> OnboardingSlot:
        async with self._writes.begin() as conn:
            await conn.execute(sa.insert(slots).values(**slot.model_dump()))
        return slot

    async def get_slot(self, slot_id: str) -> OnboardingSlot | None:
        async with self.engine.connect() as conn:
            row = (await conn.execute(sa.select(slots).where(slots.c.id == slot_id))).first()
        return OnboardingSlot.model_validate(row._mapping) if row else None

    async def list_open_slots(self, after: datetime, limit: int = 10) -> list[OnboardingSlot]:
        """Slots starting at/after `after` that still have capacity, soonest first."""
        query = (
            sa.select(slots)
            .where(slots.c.starts_at >= after, slots.c.booked < slots.c.capacity)
            .order_by(slots.c.starts_at)
            .limit(limit)
        )
        async with self.engine.connect() as conn:
            return [OnboardingSlot.model_validate(r._mapping) for r in await conn.execute(query)]

    async def book_slot(self, screening_id: str, slot_id: str) -> BookingResult:
        try:
            return await self._try_book(screening_id, slot_id)
        except IntegrityError:
            # Lost a race on the unique key (another transaction booked this screening
            # between our check and insert): the outcome is now readable.
            async with self.engine.connect() as conn:
                existing = await self._booked_slot(conn, screening_id)
            if existing is None:
                raise  # not a race: e.g. the screening does not exist
            return self._already(existing, slot_id)

    @staticmethod
    def _already(existing_slot_id: str, slot_id: str) -> BookingResult:
        if existing_slot_id == slot_id:
            return BookingResult.ALREADY_BOOKED
        return BookingResult.HAS_OTHER_SLOT

    @staticmethod
    async def _booked_slot(conn: AsyncConnection, screening_id: str) -> str | None:
        query = sa.select(bookings.c.slot_id).where(bookings.c.screening_id == screening_id)
        return (await conn.execute(query)).scalar_one_or_none()

    async def _try_book(self, screening_id: str, slot_id: str) -> BookingResult:
        async with self._writes.begin() as conn:
            if (existing := await self._booked_slot(conn, screening_id)) is not None:
                return self._already(existing, slot_id)
            found = await conn.execute(sa.select(slots.c.id).where(slots.c.id == slot_id))
            if found.first() is None:
                return BookingResult.NOT_FOUND
            taken = await conn.execute(
                sa.update(slots)
                .where(slots.c.id == slot_id, slots.c.booked < slots.c.capacity)
                .values(booked=slots.c.booked + 1)
            )
            if taken.rowcount == 0:
                return BookingResult.FULL
            await conn.execute(
                sa.insert(bookings).values(
                    screening_id=screening_id, slot_id=slot_id, created_at=utcnow()
                )
            )
            return BookingResult.BOOKED


# --- helpers --------------------------------------------------------------------------


def _in_enum_order[E: StrEnum](enum: type[E], values: Sequence[str]) -> list[E]:
    """Parse stored strings, in the enum's definition order (the linking tables are sets)."""
    wanted = set(values)
    return [member for member in enum if member.value in wanted]


def _distinct_in_enum_order(values: Sequence[Subject]) -> list[Subject]:
    return _in_enum_order(Subject, [v.value for v in values])


async def _values_by_owner(
    conn: AsyncConnection,
    table: sa.Table,
    owner_column: str,
    value_column: str,
    owner_ids: Sequence[str],
) -> dict[str, list[str]]:
    """The values of a linking table per owner id (one query)."""
    found: dict[str, list[str]] = {}
    if not owner_ids:
        return found
    query = sa.select(table.c[owner_column], table.c[value_column]).where(
        table.c[owner_column].in_(owner_ids)
    )
    for owner, value in await conn.execute(query):
        found.setdefault(owner, []).append(value)
    return found


async def _insert_values(
    conn: AsyncConnection,
    table: sa.Table,
    owner_column: str,
    owner_id: str,
    value_column: str,
    values: Sequence[StrEnum],
) -> None:
    """Insert one row per distinct value (no-op for an empty list)."""
    if rows := [{owner_column: owner_id, value_column: v.value} for v in dict.fromkeys(values)]:
        await conn.execute(sa.insert(table), rows)


async def _replace_values(
    conn: AsyncConnection,
    table: sa.Table,
    screening_id: str,
    value_column: str,
    values: Sequence[StrEnum],
) -> None:
    """Replace a screening's list fact, inside the caller's write transaction."""
    await conn.execute(sa.delete(table).where(table.c.screening_id == screening_id))
    await _insert_values(conn, table, "screening_id", screening_id, value_column, values)


async def _upsert_facts(conn: AsyncConnection, screening_id: str, **values: Any) -> None:
    """Set the given scalar facts (and updated_at), creating the facts row on first use.
    Portable: UPDATE first, INSERT when no row matched (writers are serialized)."""
    values["updated_at"] = utcnow()
    updated = await conn.execute(
        sa.update(screening_facts)
        .where(screening_facts.c.screening_id == screening_id)
        .values(**values)
    )
    if updated.rowcount == 0:
        await conn.execute(sa.insert(screening_facts).values(screening_id=screening_id, **values))
