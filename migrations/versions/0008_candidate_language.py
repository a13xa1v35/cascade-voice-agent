"""Per-candidate call language

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-12 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Nullable: NULL means the app-wide LANGUAGE setting."""
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("language", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("language")
