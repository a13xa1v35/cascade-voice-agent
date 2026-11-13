"""Referred questions replace the WhatsApp answer requests

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Every answer request becomes a referred question (`automatic` is the
    negation of the old `consent`); the answer-job columns, the summary's `answer_requested`
    and the old metrics name go away."""
    op.create_table(
        "referred_questions",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("screening_id", sa.String(length=12), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("automatic", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screenings.id"],
            name=op.f("fk_referred_questions_screening_id_screenings"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referred_questions")),
    )
    with op.batch_alter_table("referred_questions", schema=None) as batch_op:
        batch_op.create_index("ix_referred_questions_screening_id", ["screening_id"], unique=False)

    # Rows from before the language column have none: the default call language.
    op.execute(
        "INSERT INTO referred_questions (id, screening_id, question, automatic, language, "
        "created_at) SELECT id, screening_id, question, NOT consent, COALESCE(language, 'en'), "
        "created_at FROM answer_requests"
    )

    with op.batch_alter_table("answer_requests", schema=None) as batch_op:
        batch_op.drop_index("ix_answer_requests_screening_id")
        batch_op.drop_index("ix_answer_requests_status")
    op.drop_table("answer_requests")

    with op.batch_alter_table("summaries") as batch:
        batch.drop_column("answer_requested")
    with op.batch_alter_table("call_metrics") as batch:
        batch.alter_column("answer_requests_created", new_column_name="questions_referred")


def downgrade() -> None:
    """Downgrade schema. The lost columns get defaults: the rows come back as `needs_human`
    on WhatsApp, `consent` false, no answer."""
    with op.batch_alter_table("call_metrics") as batch:
        batch.alter_column("questions_referred", new_column_name="answer_requests_created")
    with op.batch_alter_table("summaries") as batch:
        batch.add_column(
            sa.Column("answer_requested", sa.JSON(), nullable=False, server_default="[]")
        )

    op.create_table(
        "answer_requests",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("screening_id", sa.String(length=12), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("kb_version", sa.String(), nullable=True),
        sa.Column("chunk_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screenings.id"],
            name=op.f("fk_answer_requests_screening_id_screenings"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_answer_requests")),
    )
    with op.batch_alter_table("answer_requests", schema=None) as batch_op:
        batch_op.create_index("ix_answer_requests_screening_id", ["screening_id"], unique=False)
        batch_op.create_index("ix_answer_requests_status", ["status"], unique=False)

    op.execute(
        "INSERT INTO answer_requests (id, screening_id, question, channel, consent, language, "
        "status, chunk_ids, created_at) SELECT id, screening_id, question, 'whatsapp', FALSE, "
        "language, 'needs_human', '[]', created_at FROM referred_questions"
    )

    with op.batch_alter_table("referred_questions", schema=None) as batch_op:
        batch_op.drop_index("ix_referred_questions_screening_id")
    op.drop_table("referred_questions")
