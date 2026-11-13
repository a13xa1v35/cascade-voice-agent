"""In-call frustration check in call_metrics

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_COLUMNS = (
    ("frustration_checks", sa.Integer()),
    ("frustration_max", sa.Float()),
    ("frustration_frustrated_checks", sa.Integer()),
)


def upgrade() -> None:
    """Upgrade schema. Nullable: calls recorded before this migration, or without the check,
    have no values."""
    with op.batch_alter_table("call_metrics") as batch:
        for name, type_ in NEW_COLUMNS:
            batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("call_metrics") as batch:
        for name, _ in reversed(NEW_COLUMNS):
            batch.drop_column(name)
