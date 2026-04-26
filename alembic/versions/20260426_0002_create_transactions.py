"""create transactions table

Revision ID: 20260426_0002
Revises: 20260426_0001
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_0002"
down_revision: str | None = "20260426_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("merchant_mcc", sa.String(length=16), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("category_confidence", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("satisfaction_score", sa.Integer(), nullable=True),
        sa.Column("satisfaction_text", sa.String(length=500), nullable=True),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_chatbot_session_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_external_id", "transactions", ["external_id"], unique=True)
    op.create_index("ix_transactions_user_occurred", "transactions", ["user_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_user_occurred", table_name="transactions")
    op.drop_index("ix_transactions_external_id", table_name="transactions")
    op.drop_table("transactions")
