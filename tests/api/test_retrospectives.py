from datetime import UTC, date, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_retrospective_service
from app.core.enums import Category, RetrospectiveSelectionReason
from app.models.user import User
from app.schemas.retrospective import (
    CurrentWeekRetrospectiveResponse,
    RetrospectiveHistoryItem,
    RetrospectiveHistoryResponse,
    RetrospectiveTransactionItem,
    SubmitRetrospectiveResponse,
    WeeklyInsight,
)


class FakeRetrospectiveService:
    async def get_current_week(self, user: User):
        return CurrentWeekRetrospectiveResponse(
            week_start=date(2026, 4, 20),
            week_end=date(2026, 4, 26),
            is_completed=False,
            transactions=[
                RetrospectiveTransactionItem(
                    transaction_id="t_1",
                    amount=35000,
                    merchant="스타벅스",
                    category=Category.IMMEDIATE,
                    occurred_at=datetime(2026, 4, 25, 19, 30, tzinfo=UTC),
                    selection_reason=RetrospectiveSelectionReason.DIVERSITY,
                    linked_chatbot_summary=None,
                )
            ],
        )

    async def submit_retrospective(self, user: User, request):
        return SubmitRetrospectiveResponse(
            retrospective_id="r_test",
            week_start=request.week_start,
            completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
            submitted_count=len(request.entries),
            weekly_insight=WeeklyInsight(headline="이번 주 만족도 평균 4.0점", highlight="즉시 소비"),
        )

    async def list_retrospectives(self, **kwargs):
        return RetrospectiveHistoryResponse(
            retrospectives=[
                RetrospectiveHistoryItem(
                    retrospective_id="r_test",
                    week_start=date(2026, 4, 20),
                    week_end=date(2026, 4, 26),
                    completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
                    avg_score=4.0,
                    entry_count=2,
                )
            ],
            next_cursor=None,
        )


async def fake_current_user():
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def install_retrospective_overrides(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_retrospective_service] = FakeRetrospectiveService


def test_get_current_week_retrospective_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.get("/v1/retrospectives/current-week")

    assert response.status_code == 200
    assert response.json()["data"]["week_start"] == "2026-04-20"
    assert response.json()["data"]["transactions"][0]["selection_reason"] == "DIVERSITY"


def test_submit_retrospective_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.post(
        "/v1/retrospectives",
        json={"week_start": "2026-04-20", "entries": [{"transaction_id": "t_1", "score": 4, "text": None}]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["retrospective_id"] == "r_test"
    assert response.json()["data"]["submitted_count"] == 1


def test_list_retrospectives_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.get("/v1/retrospectives")

    assert response.status_code == 200
    assert response.json()["data"]["retrospectives"][0]["avg_score"] == 4.0
