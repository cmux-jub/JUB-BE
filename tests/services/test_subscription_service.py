from datetime import UTC, datetime

import pytest

from app.core.enums import OnboardingStatus, SubscriptionPlan, SubscriptionTier
from app.models.subscription import Subscription, create_subscription_id
from app.models.user import User
from app.schemas.subscription import UpgradeSubscriptionRequest
from app.services.subscription_service import SubscriptionService


class FakeSubscriptionRepository:
    def __init__(self, subscription: Subscription | None = None) -> None:
        self.subscription = subscription

    async def find_by_user_id(self, user_id: str):
        if self.subscription is None or self.subscription.user_id != user_id:
            return None
        return self.subscription

    async def save(self, subscription: Subscription):
        if subscription.id is None:
            subscription.id = create_subscription_id()
        self.subscription = subscription
        return subscription


class FakeUserRepository:
    async def save(self, user: User):
        return user


def create_user(tier: SubscriptionTier = SubscriptionTier.FREE_FULL, usage_count: int = 2) -> User:
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password="hashed",
        nickname="tester",
        birth_year=1998,
        onboarding_status=OnboardingStatus.READY.value,
        subscription_tier=tier.value,
        chatbot_usage_count=usage_count,
    )


@pytest.mark.asyncio
async def test_get_subscription_status_returns_free_remaining_count():
    service = SubscriptionService(FakeSubscriptionRepository(), FakeUserRepository())

    result = await service.get_status(create_user(usage_count=3))

    assert result.tier == SubscriptionTier.FREE_FULL
    assert result.chatbot_full_remaining == 2
    assert result.next_billing_date is None


@pytest.mark.asyncio
async def test_upgrade_subscription_marks_user_as_paid():
    service = SubscriptionService(FakeSubscriptionRepository(), FakeUserRepository())
    user = create_user()

    result = await service.upgrade(
        user,
        UpgradeSubscriptionRequest(plan=SubscriptionPlan.MONTHLY, payment_method_token="pm_test"),
    )

    assert user.subscription_tier == SubscriptionTier.PAID.value
    assert result.tier == SubscriptionTier.PAID
    assert result.chatbot_full_remaining == 0
    assert result.next_billing_date is not None


@pytest.mark.asyncio
async def test_get_subscription_status_uses_existing_billing_date():
    subscription = Subscription(
        id="sub_test",
        user_id="u_test",
        tier=SubscriptionTier.PAID.value,
        plan=SubscriptionPlan.MONTHLY.value,
        next_billing_date=datetime(2026, 5, 26, tzinfo=UTC),
    )
    service = SubscriptionService(FakeSubscriptionRepository(subscription), FakeUserRepository())

    result = await service.get_status(create_user(SubscriptionTier.PAID, usage_count=10))

    assert result.next_billing_date == datetime(2026, 5, 26, tzinfo=UTC)
