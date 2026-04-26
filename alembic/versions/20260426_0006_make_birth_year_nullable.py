"""make user birth year nullable

Revision ID: 20260426_0006
Revises: 20260426_0005
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_0006"
down_revision: str | None = "20260426_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "birth_year", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "birth_year", existing_type=sa.Integer(), nullable=False)
