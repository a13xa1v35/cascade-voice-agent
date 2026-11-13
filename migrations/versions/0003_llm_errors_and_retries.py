"""LLM request errors and retries in call_metrics

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_COLUMNS = (
    ("llm_errors", sa.Integer()),
    ("llm_retries", sa.Integer()),
)


def upgrade() -> None:
    """Upgrade schema. Nullable: calls recorded before this migration have no values."""
    with op.batch_alter_table("call_metrics") as batch:
        for name, type_ in NEW_COLUMNS:
            batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("call_metrics") as batch:
        for name, _ in reversed(NEW_COLUMNS):
            batch.drop_column(name)
