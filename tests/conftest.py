import fakeredis
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool
from textcall_helpers import ScriptedLLM

from hr_screener.config import Settings
from hr_screener.knowledge.store import UnavailableKnowledgeBase
from hr_screener.models import Opening, Role, Subject
from hr_screener.pipeline import bot
from hr_screener.storage.db import make_engine, metadata
from hr_screener.storage.store import ScreeningStore


@pytest.fixture(autouse=True)
def _no_settings_from_the_environment(monkeypatch):
    """`_env_file=None` keeps the real .env out, but Settings also reads process variables:
    an exported ANTHROPIC_API_KEY or Twilio token would change what a test exercises."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture(autouse=True)
def no_real_knowledge_base(monkeypatch):
    """The app opens its knowledge base at startup. Tests never resolve one from the
    environment (an OPENAI_API_KEY exported in the shell would mean network, fastembed and an
    embedded Qdrant folder): they get the unavailable stand-in unless they inject their own."""

    async def unavailable(settings, **kwargs):
        return UnavailableKnowledgeBase("tests")

    monkeypatch.setattr("hr_screener.app.api.open_knowledge_base", unavailable)
    monkeypatch.setattr("hr_screener.cli.chat.open_knowledge_base", unavailable)


@pytest.fixture
def settings(tmp_path) -> Settings:
    # _env_file=None: tests must never pick up a developer's real .env
    return Settings(
        _env_file=None,
        timezone="UTC",
        call_log_dir=str(tmp_path),
    )


@pytest_asyncio.fixture
async def engine(tmp_path):
    """SQLite file per test with the schema created straight from the metadata (the
    migration test covers Alembic).

    A file rather than in-memory + StaticPool: the API tests cancel request handlers in the
    middle of a query (a websocket closing), and cancelling a statement on the one shared
    in-memory connection discards that connection, and the database with it.

    NullPool: the engine is used from several event loops (this fixture's, TestClient's
    portal thread, asyncio.run in sync tests), and a pooled connection reused on a loop other
    than the one that opened it can hang. A fresh connection per checkout avoids that.
    """
    eng = make_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db", poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def redis() -> Redis:
    """Fake Redis: only the per-call event timeline lives there."""
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def store(engine: AsyncEngine, redis: Redis) -> ScreeningStore:
    return ScreeningStore(engine, redis)


@pytest_asyncio.fixture
async def opening(store: ScreeningStore) -> Opening:
    """A tutor opening in Madrid that needs math, physics or computer science, 14-day window."""
    return await store.create_opening(
        Opening(
            role=Role.TUTOR,
            location="Madrid",
            qualify_window_days=14,
            subjects=[Subject.MATH, Subject.PHYSICS, Subject.COMPUTER_SCIENCE],
        )
    )


@pytest.fixture
def text_settings(settings: Settings) -> Settings:
    # Only the LLM key: the text channel needs no STT/TTS keys.
    return settings.model_copy(update={"anthropic_api_key": "x"})


@pytest.fixture
def script_llm(monkeypatch):
    def install(script) -> ScriptedLLM:
        llm = ScriptedLLM(script)
        monkeypatch.setattr(bot, "make_llm", lambda settings, prompt, **kw: llm)
        return llm

    return install
