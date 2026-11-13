"""The Alembic migrations build exactly the schema in hr_screener.storage.db (no drift)."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from hr_screener.storage.db import metadata

ROOT = Path(__file__).resolve().parents[1]


def alembic_config(db_file: Path) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file}")
    return cfg


def table_names(db_file: Path) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db_file}")
    try:
        return set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_matches_metadata_and_downgrade_works(tmp_path):
    db_file = tmp_path / "var" / "migrated.db"
    cfg = alembic_config(db_file)

    command.upgrade(cfg, "head")
    assert table_names(db_file) == set(metadata.tables)

    engine = sa.create_engine(f"sqlite:///{db_file}")
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"compare_type": True})
            assert compare_metadata(context, metadata) == []
    finally:
        engine.dispose()

    command.check(cfg)  # same check as `alembic check`
    command.downgrade(cfg, "base")
    assert table_names(db_file) == set()
