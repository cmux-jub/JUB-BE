from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import ChatbotMessageRole, ChatbotModelTier


def create_chatbot_session_id() -> str:
    return f"sess_{token_urlsafe(16)}"


def create_chatbot_message_id() -> str:
    return f"msg_{token_urlsafe(16)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChatbotSession(Base):
    __tablename__ = "chatbot_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=create_chatbot_session_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    initial_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    amount_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_tier: Mapped[str] = mapped_column(String(16), nullable=False, default=ChatbotModelTier.FULL.value)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    linked_transaction_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=create_chatbot_message_id)
    session_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("chatbot_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ChatbotMessageRole.USER.value)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    data_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
