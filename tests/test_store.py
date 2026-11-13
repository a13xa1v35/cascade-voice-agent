import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hr_screener.models import (
    Candidate,
    OnboardingSlot,
    Opening,
    Role,
    Screening,
    ScreeningStatus,
    SlotMode,
)
from hr_screener.storage.db import make_engine, metadata
from hr_screener.storage.store import BookingResult, ScreeningStore

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


async def make_screening(store: ScreeningStore, opening: Opening) -> Screening:
    candidate = await store.create_candidate(
        Candidate(name="Jo Doe", phone="+15550001111", location="Madrid", opening_id=opening.id)
    )
    return await store.create_screening(Screening(candidate_id=candidate.id, channel="webrtc"))


async def test_transition_status_is_compare_and_set(store: ScreeningStore, opening: Opening):
    screening = await make_screening(store, opening)
    pending, running = ScreeningStatus.PENDING, ScreeningStatus.IN_PROGRESS
    assert await store.transition_status(screening.id, pending, running)
    assert not await store.transition_status(screening.id, pending, running)
    assert not await store.transition_status("missing", pending, running)


async def test_open_slots_are_ordered_and_filtered(store: ScreeningStore, opening: Opening):
    later = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=2), mode=SlotMode.ONLINE, capacity=2)
    )
    sooner = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=1), mode=SlotMode.ONLINE, capacity=2)
    )
    past = await store.create_slot(
        OnboardingSlot(starts_at=NOW - timedelta(days=1), mode=SlotMode.ONLINE, capacity=2)
    )
    full = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(hours=5), mode=SlotMode.ONLINE, capacity=1)
    )
    screening = await make_screening(store, opening)
    assert await store.book_slot(screening.id, full.id) is BookingResult.BOOKED

    open_slots = await store.list_open_slots(NOW, limit=10)
    assert [s.id for s in open_slots] == [sooner.id, later.id]
    assert past.id not in [s.id for s in open_slots]
    assert len(await store.list_open_slots(NOW, limit=1)) == 1


async def test_booking_capacity_and_idempotency(store: ScreeningStore, opening: Opening):
    slot = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=1), mode=SlotMode.ONLINE, capacity=1)
    )
    first, second = await make_screening(store, opening), await make_screening(store, opening)

    assert await store.book_slot(first.id, slot.id) is BookingResult.BOOKED
    assert await store.book_slot(first.id, slot.id) is BookingResult.ALREADY_BOOKED
    assert await store.book_slot(second.id, slot.id) is BookingResult.FULL
    assert await store.book_slot(second.id, "nope") is BookingResult.NOT_FOUND

    loaded = await store.get_slot(slot.id)
    assert loaded is not None
    assert loaded.booked == 1  # the repeat did not consume a second seat
    screening = await store.get_screening(first.id)
    assert screening is not None
    assert screening.slot_id == slot.id


@pytest.fixture
async def file_store(tmp_path, redis):
    """A store on a real SQLite file (WAL, BEGIN IMMEDIATE, pooled connections), so
    concurrent bookers can actually race, unlike a single shared in-memory connection."""
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/race.db")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield ScreeningStore(engine, redis)
    await engine.dispose()


@pytest.mark.parametrize("capacity", [1, 4])
async def test_concurrent_booking_never_oversells(file_store: ScreeningStore, capacity: int):
    store = file_store
    opening = await store.create_opening(Opening(role=Role.TUTOR, location="Madrid"))
    slot = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=1), mode=SlotMode.ONLINE, capacity=capacity)
    )
    screenings = [await make_screening(store, opening) for _ in range(10)]

    results = await asyncio.gather(*(store.book_slot(s.id, slot.id) for s in screenings))

    assert results.count(BookingResult.BOOKED) == capacity
    assert results.count(BookingResult.FULL) == 10 - capacity
    loaded = await store.get_slot(slot.id)
    assert loaded is not None
    assert loaded.booked == capacity
    held = [await store.get_screening(s.id) for s in screenings]
    booked_ids = [h.id for h in held if h is not None and h.slot_id == slot.id]
    assert len(booked_ids) == capacity


async def test_cannot_hold_two_slots(store: ScreeningStore, opening: Opening):
    a = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=1), mode=SlotMode.ONLINE)
    )
    b = await store.create_slot(
        OnboardingSlot(starts_at=NOW + timedelta(days=2), mode=SlotMode.ONLINE)
    )
    screening = await make_screening(store, opening)
    assert await store.book_slot(screening.id, a.id) is BookingResult.BOOKED
    assert await store.book_slot(screening.id, b.id) is BookingResult.HAS_OTHER_SLOT
    slot_b = await store.get_slot(b.id)
    assert slot_b is not None
    assert slot_b.booked == 0


async def test_datetimes_roundtrip_as_utc_aware(store: ScreeningStore, opening: Opening):
    madrid = ZoneInfo("Europe/Madrid")
    local = datetime(2026, 11, 12, 17, 30, tzinfo=madrid)
    slot = await store.create_slot(OnboardingSlot(starts_at=local, mode=SlotMode.ONLINE))
    loaded = await store.get_slot(slot.id)
    assert loaded is not None
    assert loaded.starts_at.tzinfo is not None
    assert loaded.starts_at.utcoffset() == timedelta(0)  # normalised to UTC
    assert loaded.starts_at == local  # same instant
    assert loaded.starts_at.hour == 16

    screening = await make_screening(store, opening)
    again = await store.get_screening(screening.id)
    assert again is not None
    assert again.created_at.tzinfo is not None
    assert again.created_at == screening.created_at
    # Filtering compares instants, whatever zone the caller uses.
    assert [s.id for s in await store.list_open_slots(local - timedelta(minutes=1))] == [slot.id]
    assert await store.list_open_slots(local + timedelta(minutes=1)) == []
