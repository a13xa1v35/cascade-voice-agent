"""Create a demo opening, a candidate on it and some onboarding slots.

uv run python -m hr_screener.app.seed [--reset] [--name "Alex"] [--phone +15551234567]

--reset first deletes every row of this app's tables and the Redis event timeline of each
screening in this database (never FLUSHDB, never a key pattern: Redis may be shared by
several checkouts, whose timelines stay), so reseeding starts clean. Run `make migrate`
first to create the schema.
"""

import argparse
import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from redis.exceptions import RedisError

from hr_screener.config import Settings
from hr_screener.models import Candidate, OnboardingSlot, Opening, Role, SlotMode, Subject
from hr_screener.storage.db import make_engine
from hr_screener.storage.store import ScreeningStore, events_key

# The demo opening: what the old DEFAULT_* / NEEDED_SUBJECTS / QUALIFY_WINDOW_DAYS settings held.
DEMO_ROLE = Role.TUTOR
DEMO_LOCATION = "Madrid"
DEMO_NEEDED_SUBJECTS = (Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE)
DEMO_WINDOW_DAYS = 14
# What the demo candidate declares when applying.
DEMO_DECLARED_SUBJECTS = (Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE)

SLOT_HOURS = (10, 17)  # local hours, two sessions a day (tutoring-friendly)
SLOT_COUNT = 6
# (mode, address) pairs, alternating; the wording is translated by hr_screener.i18n
SLOT_PLACES = ((SlotMode.IN_PERSON, "Chamberí, Madrid"), (SlotMode.ONLINE, None))


async def reset_redis(redis: Redis, screening_ids: list[str]) -> int:
    """Delete the event timelines of exactly these screenings. Returns how many existed."""
    deleted = 0
    for i in range(0, len(screening_ids), 500):
        keys = [events_key(sid) for sid in screening_ids[i : i + 500]]
        deleted += await redis.delete(*keys)
    return deleted


async def reset(store: ScreeningStore) -> int:
    """Empty the SQL tables, then delete this database's call timelines from Redis. Returns
    how many Redis keys went. The ids are read first: the Redis may be shared with other
    checkouts, so keys are deleted by id, never by pattern. Redis being down only warns: the
    SQL data is the part that matters."""
    screening_ids = await store.list_screening_ids()
    await store.reset_all()
    try:
        return await reset_redis(store.redis, screening_ids)
    except RedisError as exc:
        print(f"warning: could not clear Redis event keys ({exc}); SQL tables were reset")
        return 0


async def demo_opening(store: ScreeningStore) -> Opening:
    """The demo opening, reused when it already exists so reseeding does not pile up copies."""
    for opening in await store.list_openings():
        if (
            opening.role is DEMO_ROLE
            and opening.location == DEMO_LOCATION
            and opening.qualify_window_days == DEMO_WINDOW_DAYS
            and set(opening.subjects) == set(DEMO_NEEDED_SUBJECTS)
        ):
            return opening
    return await store.create_opening(
        Opening(
            role=DEMO_ROLE,
            location=DEMO_LOCATION,
            qualify_window_days=DEMO_WINDOW_DAYS,
            subjects=list(DEMO_NEEDED_SUBJECTS),
        )
    )


async def add_slots(
    store: ScreeningStore,
    settings: Settings,
    count: int,
    taken: frozenset[datetime] = frozenset(),
) -> None:
    """Create `count` onboarding slots on the coming working days, starting tomorrow (local
    time), skipping the start times in `taken`."""
    tz = ZoneInfo(settings.timezone)
    day = datetime.now(tz).date() + timedelta(days=1)
    created = 0
    while created < count:
        if day.weekday() < 5:  # working days only
            for hour in SLOT_HOURS:
                starts_at = datetime.combine(day, time(hour), tz)
                if created == count:
                    break
                if starts_at in taken:
                    continue
                mode, address = SLOT_PLACES[created % len(SLOT_PLACES)]
                await store.create_slot(
                    OnboardingSlot(starts_at=starts_at, mode=mode, address=address, capacity=5)
                )
                created += 1
        day += timedelta(days=1)


async def ensure_demo_data(store: ScreeningStore, settings: Settings, min_slots: int) -> Opening:
    """Idempotent setup for the public demo: the demo opening, and at least `min_slots`
    future slots with room (booked-out or past ones are replaced by new dates)."""
    opening = await demo_opening(store)
    open_slots = await store.list_open_slots(datetime.now(ZoneInfo(settings.timezone)), limit=1000)
    if len(open_slots) < min_slots:
        await add_slots(
            store,
            settings,
            min_slots - len(open_slots),
            frozenset(s.starts_at for s in open_slots),
        )
    return opening


async def seed(store: ScreeningStore, settings: Settings, name: str, phone: str) -> Candidate:
    opening = await demo_opening(store)
    candidate = await store.create_candidate(
        Candidate(
            name=name,
            phone=phone,
            location=opening.location,
            opening_id=opening.id,
            subjects=list(DEMO_DECLARED_SUBJECTS),
        )
    )

    await add_slots(store, settings, SLOT_COUNT)
    return candidate


async def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="delete this app's rows and keys first"
    )
    parser.add_argument("--name", default="Alex")
    parser.add_argument("--phone", default=settings.demo_candidate_phone)
    args = parser.parse_args()

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = make_engine(settings.database_url)
    try:
        store = ScreeningStore(engine, redis)
        if args.reset:
            print(f"Reset: emptied the tables, deleted {await reset(store)} Redis event keys")
        candidate = await seed(store, settings, args.name, args.phone)
    finally:
        await engine.dispose()
        await redis.aclose()
    print(f"Seeded {SLOT_COUNT} slots and candidate {candidate.name}")
    print(f"candidate id: {candidate.id}")
    print("The web UI and `make chat` use the most recent candidate: nothing to set.")


if __name__ == "__main__":
    asyncio.run(main())
