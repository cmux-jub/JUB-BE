from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_subscription_service
from app.core.enums import OnboardingStatus, SubscriptionTier
from app.models.user import User
from app.schemas.subscription import SubscriptionStatusResponse


class FakeSubscriptionService:
    async def get_status(self, user: User):
        return SubscriptionStatusResponse(
            tier=SubscriptionTier.FREE_FULL,
            chatbot_usage_count=3,
            chatbot_full_remaining=2,
            downgrades_at=None,
            next_billing_date=None,
        )

    async def upgrade(self, user: User, request):
        return SubscriptionStatusResponse(
            tier=SubscriptionTier.PAID,
            chatbot_usage_count=user.chatbot_usage_count,
            chatbot_full_remaining=0,
            downgrades_at=None,
            next_billing_date=datetime(2026, 5, 26, tzinfo=UTC),
        )


async def fake_current_user():
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password="hashed",
        nickname="tester",
        birth_year=1998,
        onboarding_status=OnboardingStatus.READY.value,
        subscription_tier=SubscriptionTier.FREE_FULL.value,
        chatbot_usage_count=3,
    )


def install_subscription_overrides(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_subscription_service] = FakeSubscriptionService


def test_get_subscription_status_success(app: FastAPI, client: TestClient):
    install_subscription_overrides(app)

    response = client.get("/v1/subscription")

    assert response.status_code == 200
    assert response.json()["data"]["chatbot_full_remaining"] == 2


def test_upgrade_subscription_success(app: FastAPI, client: TestClient):
    install_subscription_overrides(app)

    response = client.post("/v1/subscription/upgrade", json={"plan": "MONTHLY", "payment_method_token": "pm_test"})

    assert response.status_code == 200
    assert response.json()["data"]["tier"] == "PAID"
    assert response.json()["data"]["next_billing_date"] is not None
