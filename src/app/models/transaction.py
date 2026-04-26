from datetime import UTC, datetime
from secrets import token_urlsafe

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import Category


def create_transaction_id() -> str:
    return f"t_{token_urlsafe(16)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=create_transaction_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_mcc: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default=Category.LASTING.value)
    category_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    satisfaction_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    satisfaction_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_chatbot_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
