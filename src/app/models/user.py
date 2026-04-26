from datetime import UTC, datetime
from secrets import token_urlsafe

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import OnboardingStatus, SubscriptionTier


def create_user_id() -> str:
    return f"u_{token_urlsafe(16)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=create_user_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OnboardingStatus.NEEDS_BANK_LINK.value,
    )
    subscription_tier: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SubscriptionTier.FREE_FULL.value,
    )
    chatbot_usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
