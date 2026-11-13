"""Frustration signals in summaries

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Nullable: NULL means not assessed (a fallback summary, or a summary
    written before this migration)."""
    with op.batch_alter_table("summaries") as batch:
        batch.add_column(sa.Column("frustration_signals", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("summaries") as batch:
        batch.drop_column("frustration_signals")
