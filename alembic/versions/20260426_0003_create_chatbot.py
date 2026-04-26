"""create chatbot tables

Revision ID: 20260426_0003
Revises: 20260426_0002
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_0003"
down_revision: str | None = "20260426_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chatbot_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("initial_message", sa.String(length=1000), nullable=False),
        sa.Column("amount_hint", sa.Integer(), nullable=True),
        sa.Column("product_hint", sa.String(length=255), nullable=True),
        sa.Column("model_tier", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("linked_transaction_id", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["linked_transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_sessions_user_started", "chatbot_sessions", ["user_id", "started_at"])

    op.create_table(
        "chatbot_messages",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column("data_references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chatbot_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_messages_session_created", "chatbot_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_chatbot_messages_session_created", table_name="chatbot_messages")
    op.drop_table("chatbot_messages")
    op.drop_index("ix_chatbot_sessions_user_started", table_name="chatbot_sessions")
    op.drop_table("chatbot_sessions")
