from datetime import UTC, date, datetime
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def create_retrospective_id() -> str:
    return f"r_{token_urlsafe(16)}"


def create_retrospective_entry_id() -> str:
    return f"re_{token_urlsafe(16)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Retrospective(Base):
    __tablename__ = "retrospectives"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_retrospectives_user_week"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=create_retrospective_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_insight: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class RetrospectiveEntry(Base):
    __tablename__ = "retrospective_entries"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=create_retrospective_entry_id)
    retrospective_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("retrospectives.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
