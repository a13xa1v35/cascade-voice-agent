"""`make reseed` deletes only its own database's call timelines: several checkouts share one
Redis, and a reset must never wipe another checkout's calls."""

from redis.asyncio import Redis

from hr_screener.app.seed import reset, seed
from hr_screener.config import Settings
from hr_screener.models import Channel, Screening
from hr_screener.storage.store import ScreeningStore


async def test_reset_leaves_other_checkouts_timelines_alone(
    redis: Redis, store: ScreeningStore, settings: Settings
):
    candidate = await seed(store, settings, "Alex", "+34600000000")
    ours = await store.create_screening(
        Screening(candidate_id=candidate.id, channel=Channel.WEBRTC)
    )
    await redis.rpush(f"screening:{ours.id}:events", "{}")
    await redis.rpush("screening:from-another-checkout:events", "{}")

    assert await reset(store) == 1

    assert await redis.keys("*") == ["screening:from-another-checkout:events"]
