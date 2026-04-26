from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_auth_service, get_current_user
from app.core.enums import OnboardingStatus, SubscriptionTier
from app.models.user import User
from app.schemas.auth import AuthTokenResponse, TokenRefreshResponse


class FakeAuthService:
    async def signup(self, request):
        return AuthTokenResponse(
            user_id="u_test",
            access_token=f"access:{request.email}",
            refresh_token=f"refresh:{request.email}",
            onboarding_status=OnboardingStatus.NEEDS_BANK_LINK,
        )

    async def login(self, request):
        return AuthTokenResponse(
            user_id="u_test",
            access_token=f"access:{request.email}",
            refresh_token=f"refresh:{request.email}",
            onboarding_status=OnboardingStatus.NEEDS_BANK_LINK,
        )

    async def refresh(self, request):
        return TokenRefreshResponse(
            access_token=f"access:{request.refresh_token}",
            refresh_token=f"refresh:{request.refresh_token}",
        )


def test_signup_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_auth_service] = FakeAuthService

    response = client.post(
        "/v1/auth/signup",
        json={
            "email": "USER@example.com",
            "password": "password123",
            "nickname": "tester",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user_id"] == "u_test"
    assert body["data"]["access_token"] == "access:user@example.com"
    assert body["data"]["onboarding_status"] == "NEEDS_BANK_LINK"


def test_signup_rejects_birth_year_field(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_auth_service] = FakeAuthService

    response = client.post(
        "/v1/auth/signup",
        json={
            "email": "user@example.com",
            "password": "password123",
            "nickname": "tester",
            "birth_year": 1998,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_login_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_auth_service] = FakeAuthService

    response = client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["refresh_token"] == "refresh:user@example.com"


def test_refresh_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_auth_service] = FakeAuthService

    response = client.post("/v1/auth/refresh", json={"refresh_token": "refresh-token"})

    assert response.status_code == 200
    assert response.json()["data"] == {
        "access_token": "access:refresh-token",
        "refresh_token": "refresh:refresh-token",
    }


def test_users_me_requires_token(client: TestClient):
    response = client.get("/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_users_me_success(app: FastAPI, client: TestClient):
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
            created_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        )

    app.dependency_overrides[get_current_user] = fake_current_user

    response = client.get("/v1/users/me")

    assert response.status_code == 200
    assert response.json()["data"]["user_id"] == "u_test"
    assert response.json()["data"]["onboarding_status"] == "READY"
    assert response.json()["data"]["chatbot_usage_count"] == 3
