from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_banking_service, get_current_user
from app.models.user import User
from app.schemas.banking import (
    BankingSyncResponse,
    LinkedAccountResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
)


class FakeBankingService:
    def start_oauth(self, provider: str):
        return OAuthStartResponse(auth_url=f"https://mock.example/{provider}", state_token="state_test")

    def handle_callback(self, code: str, state_token: str):
        return OAuthCallbackResponse(
            linked_accounts=[
                LinkedAccountResponse(account_id="a_test", bank_name="신한은행", masked_number="****-1234")
            ]
        )

    async def sync_transactions(self, user: User, from_date: date, to_date: date):
        return BankingSyncResponse(synced_count=5, new_count=3, sync_id=f"s_{user.id}")


async def fake_current_user():
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def test_start_oauth_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_banking_service] = FakeBankingService

    response = client.post("/v1/banking/oauth/start", json={"provider": "OPEN_BANKING_KR"})

    assert response.status_code == 200
    assert response.json()["data"]["state_token"] == "state_test"


def test_oauth_callback_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_banking_service] = FakeBankingService

    response = client.post("/v1/banking/oauth/callback", json={"code": "code", "state_token": "state"})

    assert response.status_code == 200
    assert response.json()["data"]["linked_accounts"][0]["account_id"] == "a_test"


def test_banking_sync_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_banking_service] = FakeBankingService

    response = client.post("/v1/banking/sync", json={"from_date": "2026-04-20", "to_date": "2026-04-26"})

    assert response.status_code == 200
    assert response.json()["data"] == {"synced_count": 5, "new_count": 3, "sync_id": "s_u_test"}
