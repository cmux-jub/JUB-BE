from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_onboarding_service
from app.core.enums import Category, OnboardingNextStep, OnboardingSelectionReason
from app.models.user import User
from app.schemas.feedback import (
    FeedbackQuestionContent,
    FeedbackTransactionSnapshot,
    HappyArchiveItem,
    ScoreScale,
    TopHappyConsumption,
)
from app.schemas.onboarding import (
    FirstInsightResponse,
    FirstInsightSupportingData,
    OnboardingProgressResponse,
    OnboardingQuestionItem,
    OnboardingQuestionsResponse,
    OnboardingTransactionItem,
    SubmitOnboardingFeedbackResponse,
    TransactionsToLabelResponse,
)


class FakeOnboardingService:
    async def get_questions(self, user: User, limit: int = 10):
        return OnboardingQuestionsResponse(
            labeled_count=0,
            required_count=5,
            question_count=1,
            min_question_count=5,
            max_question_count=10,
            questions=[
                OnboardingQuestionItem(
                    question_id="oq_t_1",
                    transaction=FeedbackTransactionSnapshot(
                        transaction_id="t_1",
                        amount=89000,
                        merchant="유니클로",
                        category=Category.LASTING,
                        occurred_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    ),
                    selection_reason=OnboardingSelectionReason.LARGE_AMOUNT,
                    pattern_summary="큰 지출입니다.",
                    question=FeedbackQuestionContent(
                        title="만족스러웠나요?",
                        body="이 소비를 평가해 주세요.",
                        score_scale=ScoreScale(min_label="아쉬웠어요", max_label="만족스러웠어요"),
                    ),
                )
            ],
        )

    async def submit_feedback(self, user: User, request):
        return SubmitOnboardingFeedbackResponse(
            labeled_count=5,
            required_count=5,
            is_chatbot_unlocked=True,
            chatbot_context_ready=True,
            first_insight=FirstInsightResponse(
                headline="당신은 지속 소비에 쓸 때 만족도가 높네요",
                supporting_data=FirstInsightSupportingData(category="지속 소비", avg_score=4.6, count=5),
            ),
            top_happy_consumption=TopHappyConsumption(
                message="tester님의 행복 소비는 지속 소비 지출입니다.",
                category=Category.LASTING,
                category_name="지속 소비",
                avg_score=5.0,
                total_amount=89000,
                count=1,
            ),
            happy_purchase_archive=[
                HappyArchiveItem(
                    transaction_id="t_1",
                    amount=89000,
                    related_total_amount=89000,
                    merchant="유니클로",
                    category=Category.LASTING,
                    occurred_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    score=5,
                    text="좋음",
                )
            ],
        )

    async def get_transactions_to_label(self, user: User, limit: int = 10):
        return TransactionsToLabelResponse(
            labeled_count=2,
            required_count=5,
            transactions=[
                OnboardingTransactionItem(
                    transaction_id="t_1",
                    amount=89000,
                    merchant="유니클로",
                    category=Category.LASTING,
                    occurred_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    selection_reason=OnboardingSelectionReason.LARGE_AMOUNT,
                    question="이 89,000원의 유니클로, 지금 봐도 만족스러우세요?",
                )
            ],
        )

    async def get_progress(self, user: User):
        return OnboardingProgressResponse(
            labeled_count=2,
            required_count=5,
            is_chatbot_unlocked=False,
            next_step=OnboardingNextStep.LABEL_MORE,
        )

    async def create_first_insight(self, user: User):
        return FirstInsightResponse(
            headline="당신은 지속 소비에 쓸 때 만족도가 높네요",
            supporting_data=FirstInsightSupportingData(category="지속 소비", avg_score=4.6, count=5),
        )


async def fake_current_user():
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def test_get_transactions_to_label_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService

    response = client.get("/v1/onboarding/transactions-to-label?limit=10")

    assert response.status_code == 200
    assert response.json()["data"]["labeled_count"] == 2
    assert response.json()["data"]["transactions"][0]["selection_reason"] == "LARGE_AMOUNT"


def test_get_onboarding_questions_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService

    response = client.get("/v1/onboarding/questions?limit=5")

    assert response.status_code == 200
    assert response.json()["data"]["questions"][0]["question_id"] == "oq_t_1"


def test_submit_onboarding_feedback_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService

    response = client.post(
        "/v1/onboarding/feedback",
        json={"answers": [{"question_id": "oq_t_1", "transaction_id": "t_1", "score": 5, "text": "좋음"}]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_chatbot_unlocked"] is True
    assert response.json()["data"]["top_happy_consumption"]["category_name"] == "지속 소비"
    assert response.json()["data"]["happy_purchase_archive"][0]["transaction_id"] == "t_1"


def test_get_onboarding_progress_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService

    response = client.get("/v1/onboarding/progress")

    assert response.status_code == 200
    assert response.json()["data"]["next_step"] == "LABEL_MORE"
    assert response.json()["data"]["is_chatbot_unlocked"] is False


def test_create_first_insight_success(app: FastAPI, client: TestClient):
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService

    response = client.post("/v1/onboarding/first-insight")

    assert response.status_code == 200
    assert response.json()["data"]["supporting_data"]["avg_score"] == 4.6
