"""create retrospectives tables

Revision ID: 20260426_0004
Revises: 20260426_0003
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_0004"
down_revision: str | None = "20260426_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retrospectives",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avg_score", sa.Float(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("weekly_insight", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "week_start", name="uq_retrospectives_user_week"),
    )
    op.create_index("ix_retrospectives_user_week", "retrospectives", ["user_id", "week_start"])

    op.create_table(
        "retrospective_entries",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("retrospective_id", sa.String(length=32), nullable=False),
        sa.Column("transaction_id", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["retrospective_id"], ["retrospectives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrospective_entries_retrospective", "retrospective_entries", ["retrospective_id"])


def downgrade() -> None:
    op.drop_index("ix_retrospective_entries_retrospective", table_name="retrospective_entries")
    op.drop_table("retrospective_entries")
    op.drop_index("ix_retrospectives_user_week", table_name="retrospectives")
    op.drop_table("retrospectives")
