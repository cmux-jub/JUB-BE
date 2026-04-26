from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_transaction_service
from app.core.enums import Category
from app.models.user import User
from app.schemas.transaction import (
    MonthlySpendingComparison,
    SatisfactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
    TransactionSummary,
)


class FakeTransactionService:
    async def list_transactions(self, **kwargs):
        return TransactionListResponse(
            transactions=[
                TransactionSummary(
                    transaction_id="t_1",
                    amount=6500,
                    merchant="스타벅스",
                    category=Category.IMMEDIATE,
                    category_confidence=0.9,
                    occurred_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    satisfaction_score=None,
                    satisfaction_text=None,
                    labeled_at=None,
                )
            ],
            next_cursor=None,
            spending_comparison=MonthlySpendingComparison(
                current_month_amount=6500,
                previous_month_amount=4000,
                difference_amount=2500,
                difference_percent=62.5,
                difference_display="+2500",
                difference_percent_display="+62.5%",
            ),
        )

    async def get_transaction(self, user_id: str, transaction_id: str):
        return TransactionDetailResponse(
            transaction_id=transaction_id,
            amount=6500,
            merchant="스타벅스",
            merchant_mcc="5814",
            category=Category.IMMEDIATE,
            category_confidence=0.9,
            occurred_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            satisfaction_score=None,
            satisfaction_text=None,
            labeled_at=None,
            linked_chatbot_session_id=None,
        )

    async def update_category(self, user_id: str, transaction_id: str, category: Category):
        detail = await self.get_transaction(user_id, transaction_id)
        detail.category = category
        detail.category_confidence = 1.0
        return detail

    async def record_satisfaction(self, user_id: str, transaction_id: str, score: int, text: str | None):
        return SatisfactionResponse(
            transaction_id=transaction_id,
            score=score,
            text=text,
            labeled_at=datetime(2026, 4, 26, 12, 30, tzinfo=UTC),
        )


async def fake_current_user():
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def test_list_transactions_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_transaction_service] = FakeTransactionService

    response = client.get("/v1/transactions?limit=20&category=IMMEDIATE")

    assert response.status_code == 200
    assert response.json()["data"]["transactions"][0]["transaction_id"] == "t_1"
    assert response.json()["data"]["spending_comparison"]["difference_display"] == "+2500"


def test_get_transaction_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_transaction_service] = FakeTransactionService

    response = client.get("/v1/transactions/t_1")

    assert response.status_code == 200
    assert response.json()["data"]["merchant_mcc"] == "5814"


def test_update_transaction_category_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_transaction_service] = FakeTransactionService

    response = client.patch("/v1/transactions/t_1/category", json={"category": "LASTING"})

    assert response.status_code == 200
    assert response.json()["data"]["category"] == "LASTING"
    assert response.json()["data"]["category_confidence"] == 1.0


def test_record_transaction_satisfaction_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_transaction_service] = FakeTransactionService

    response = client.post("/v1/transactions/t_1/satisfaction", json={"score": 4, "text": "만족"})

    assert response.status_code == 200
    assert response.json()["data"]["score"] == 4
