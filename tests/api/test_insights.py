from datetime import UTC, date, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_insight_service
from app.core.enums import Category, OnboardingStatus, SubscriptionTier
from app.models.user import User
from app.schemas.feedback import AmountComparison, TopHappyConsumption
from app.schemas.insight import (
    CategorySatisfactionItem,
    CategorySatisfactionResponse,
    HappyPurchaseItem,
    HappyPurchasesResponse,
    MainMonthlySpendingResponse,
    MainPageSummaryResponse,
    RecentSkipItem,
    SavedAmountResponse,
    ScoreTrendPoint,
    ScoreTrendResponse,
)


class FakeInsightService:
    async def get_main_summary(self, **kwargs):
        return MainPageSummaryResponse(
            monthly_spending=MainMonthlySpendingResponse(
                current_month_amount=100000,
                previous_month_amount=200000,
                difference_amount=-100000,
                difference_percent=-50.0,
                difference_display="-100000",
                difference_percent_display="-50.0%",
            ),
            saved_amount_comparison=AmountComparison(
                current_amount=1500000,
                previous_amount=500000,
                difference_amount=1000000,
                difference_percent=200.0,
                difference_display="+1000000",
                difference_percent_display="+200.0%",
            ),
            top_happy_consumption=TopHappyConsumption(
                message="tester님의 행복 소비는 즉시 소비 지출입니다.",
                category=Category.IMMEDIATE,
                category_name="즉시 소비",
                avg_score=5.0,
                total_amount=10000,
                count=1,
            ),
            saved_amount=1500000,
            saved_count=1,
        )

    async def get_happy_purchases(self, **kwargs):
        return HappyPurchasesResponse(
            items=[
                HappyPurchaseItem(
                    transaction_id="t_1",
                    amount=10000,
                    related_total_amount=10000,
                    merchant="스타벅스",
                    category=Category.IMMEDIATE,
                    occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                    score=5,
                    text="좋음",
                )
            ],
            total_count=1,
            total_amount=10000,
            next_cursor=None,
        )

    async def get_saved_amount(self, **kwargs):
        return SavedAmountResponse(
            total_saved=1500000,
            skip_count=1,
            reconsider_count=1,
            recent_skips=[
                RecentSkipItem(
                    session_id="sess_1",
                    product="맥북",
                    amount=1500000,
                    decided_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
                )
            ],
        )

    async def get_category_satisfaction(self, **kwargs):
        return CategorySatisfactionResponse(
            categories=[CategorySatisfactionItem(name="지속 소비", avg_score=4.6, count=3, total_amount=90000)]
        )

    async def get_score_trend(self, **kwargs):
        return ScoreTrendResponse(data_points=[ScoreTrendPoint(week_start=date(2026, 4, 20), avg_score=4.1)])


async def fake_current_user():
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password="hashed",
        nickname="tester",
        birth_year=1998,
        onboarding_status=OnboardingStatus.READY.value,
        subscription_tier=SubscriptionTier.FREE_FULL.value,
        chatbot_usage_count=0,
    )


def install_insight_overrides(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_insight_service] = FakeInsightService


def test_get_happy_purchases_success(app: FastAPI, client: TestClient):
    install_insight_overrides(app)

    response = client.get("/v1/insights/happy-purchases")

    assert response.status_code == 200
    assert response.json()["data"]["total_amount"] == 10000


def test_get_main_page_summary_success(app: FastAPI, client: TestClient):
    install_insight_overrides(app)

    response = client.get("/v1/insights/main")

    assert response.status_code == 200
    assert response.json()["data"]["monthly_spending"]["difference_percent_display"] == "-50.0%"
    assert response.json()["data"]["saved_amount_comparison"]["difference_percent_display"] == "+200.0%"
    assert response.json()["data"]["top_happy_consumption"]["message"] == "tester님의 행복 소비는 즉시 소비 지출입니다."
    assert response.json()["data"]["saved_amount"] == 1500000


def test_get_saved_amount_success(app: FastAPI, client: TestClient):
    install_insight_overrides(app)

    response = client.get("/v1/insights/saved-amount?period=all")

    assert response.status_code == 200
    assert response.json()["data"]["total_saved"] == 1500000


def test_get_category_satisfaction_success(app: FastAPI, client: TestClient):
    install_insight_overrides(app)

    response = client.get("/v1/insights/category-satisfaction?period=90d")

    assert response.status_code == 200
    assert response.json()["data"]["categories"][0]["name"] == "지속 소비"


def test_get_score_trend_success(app: FastAPI, client: TestClient):
    install_insight_overrides(app)

    response = client.get("/v1/insights/score-trend?period=8w")

    assert response.status_code == 200
    assert response.json()["data"]["data_points"][0]["week_start"] == "2026-04-20"
