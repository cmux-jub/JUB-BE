from datetime import UTC, date, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_retrospective_service
from app.core.enums import Category, RetrospectiveSelectionReason
from app.models.user import User
from app.schemas.feedback import (
    AmountComparison,
    FeedbackQuestionContent,
    FeedbackTransactionSnapshot,
    HappyArchiveItem,
    ScoreScale,
    SpendingComparison,
    TopHappyConsumption,
)
from app.schemas.retrospective import (
    CurrentWeekRetrospectiveResponse,
    RetrospectiveHistoryItem,
    RetrospectiveHistoryResponse,
    RetrospectiveQuestionItem,
    SubmitRetrospectiveResponse,
    WeeklyInsight,
    WeeklySummaryResponse,
)


class FakeRetrospectiveService:
    async def get_current_week(self, user: User):
        return CurrentWeekRetrospectiveResponse(
            week_start=date(2026, 4, 20),
            week_end=date(2026, 4, 26),
            is_completed=False,
            question_count=1,
            min_question_count=5,
            max_question_count=10,
            questions=[
                RetrospectiveQuestionItem(
                    question_id="rq_t_1",
                    transaction=FeedbackTransactionSnapshot(
                        transaction_id="t_1",
                        amount=35000,
                        merchant="스타벅스",
                        category=Category.IMMEDIATE,
                        occurred_at=datetime(2026, 4, 25, 19, 30, tzinfo=UTC),
                    ),
                    selection_reason=RetrospectiveSelectionReason.DIVERSITY,
                    pattern_summary="이번 주 대표 소비입니다.",
                    question=FeedbackQuestionContent(
                        title="만족스러웠나요?",
                        body="이번 소비를 평가해 주세요.",
                        score_scale=ScoreScale(min_label="아쉬웠어요", max_label="만족스러웠어요"),
                    ),
                    linked_chatbot_summary=None,
                )
            ],
        )

    async def submit_retrospective(self, user: User, request):
        return SubmitRetrospectiveResponse(
            retrospective_id="r_test",
            week_start=request.week_start,
            completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
            submitted_count=len(request.answers),
            weekly_insight=WeeklyInsight(headline="이번 주 만족도 평균 4.0점", highlight="즉시 소비"),
        )

    async def get_weekly_summary(self, user: User, retrospective_id: str):
        return WeeklySummaryResponse(
            retrospective_id=retrospective_id,
            week_start=date(2026, 4, 20),
            week_end=date(2026, 4, 26),
            spending_comparison=SpendingComparison(
                current_amount=35000,
                previous_amount=50000,
                difference_amount=-15000,
                difference_percent=-30.0,
                difference_display="-15000",
                difference_percent_display="-30.0%",
                saved_amount=15000,
            ),
            saved_amount_comparison=AmountComparison(
                current_amount=120000,
                previous_amount=60000,
                difference_amount=60000,
                difference_percent=100.0,
                difference_display="+60000",
                difference_percent_display="+100.0%",
            ),
            top_happy_consumption=TopHappyConsumption(
                message="tester님의 행복 소비는 즉시 소비 지출입니다.",
                category=Category.IMMEDIATE,
                category_name="즉시 소비",
                avg_score=4.0,
                total_amount=35000,
                count=1,
            ),
            happy_purchase_archive=[
                HappyArchiveItem(
                    transaction_id="t_1",
                    amount=35000,
                    related_total_amount=35000,
                    merchant="스타벅스",
                    category=Category.IMMEDIATE,
                    occurred_at=datetime(2026, 4, 25, 19, 30, tzinfo=UTC),
                    score=4,
                    text=None,
                )
            ],
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
    assert response.json()["data"]["questions"][0]["selection_reason"] == "DIVERSITY"


def test_submit_retrospective_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.post(
        "/v1/retrospectives",
        json={
            "week_start": "2026-04-20",
            "answers": [{"question_id": "rq_t_1", "transaction_id": "t_1", "score": 4, "text": None}],
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["retrospective_id"] == "r_test"
    assert response.json()["data"]["submitted_count"] == 1
    assert "spending_comparison" not in response.json()["data"]
    assert "top_happy_consumption" not in response.json()["data"]


def test_get_weekly_summary_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.get("/v1/retrospectives/r_test/weekly-summary")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["retrospective_id"] == "r_test"
    assert data["spending_comparison"]["saved_amount"] == 15000
    assert data["saved_amount_comparison"]["difference_percent_display"] == "+100.0%"
    assert data["top_happy_consumption"]["category_name"] == "즉시 소비"
    assert data["happy_purchase_archive"][0]["transaction_id"] == "t_1"


def test_list_retrospectives_success(app: FastAPI, client: TestClient):
    install_retrospective_overrides(app)

    response = client.get("/v1/retrospectives")

    assert response.status_code == 200
    assert response.json()["data"]["retrospectives"][0]["avg_score"] == 4.0
