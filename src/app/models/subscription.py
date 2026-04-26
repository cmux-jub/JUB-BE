from datetime import UTC, datetime
from secrets import token_urlsafe

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import SubscriptionTier


def create_subscription_id() -> str:
    return f"sub_{token_urlsafe(16)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscriptions_user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=create_subscription_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, default=SubscriptionTier.FREE_FULL.value)
    plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    downgrades_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_billing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
