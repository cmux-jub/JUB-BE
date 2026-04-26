from datetime import UTC, date, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import (
    get_auth_service,
    get_banking_service,
    get_chatbot_service,
    get_current_user,
    get_insight_service,
    get_onboarding_service,
    get_retrospective_service,
    get_subscription_service,
)
from app.core.enums import (
    ChatbotDecision,
    ChatbotModelTier,
    OnboardingNextStep,
    OnboardingStatus,
    SubscriptionTier,
)
from app.models.user import User
from app.schemas.auth import AuthTokenResponse
from app.schemas.banking import BankingSyncResponse, LinkedAccountResponse, OAuthCallbackResponse, OAuthStartResponse
from app.schemas.chatbot import (
    ChatbotSessionListResponse,
    ChatbotSummary,
    CreateChatbotSessionResponse,
    DecideChatbotSessionResponse,
)
from app.schemas.feedback import AmountComparison, HappyArchiveItem, SpendingComparison, TopHappyConsumption
from app.schemas.insight import HappyPurchasesResponse, SavedAmountResponse
from app.schemas.onboarding import (
    FirstInsightResponse,
    FirstInsightSupportingData,
    OnboardingProgressResponse,
    SubmitOnboardingFeedbackResponse,
)
from app.schemas.retrospective import SubmitRetrospectiveResponse, WeeklyInsight, WeeklySummaryResponse
from app.schemas.subscription import SubscriptionStatusResponse
from app.schemas.transaction import MonthlySpendingComparison, TransactionListResponse


class FakeAuthService:
    async def signup(self, request):
        return AuthTokenResponse(
            user_id="u_test",
            access_token="access-token",
            refresh_token="refresh-token",
            onboarding_status=OnboardingStatus.NEEDS_BANK_LINK,
        )


class FakeBankingService:
    def start_oauth(self, provider: str):
        return OAuthStartResponse(auth_url="https://mock.example/oauth", state_token="state")

    def handle_callback(self, code: str, state_token: str):
        return OAuthCallbackResponse(
            linked_accounts=[
                LinkedAccountResponse(account_id="a_test", bank_name="신한은행", masked_number="****-1234")
            ]
        )

    async def sync_transactions(self, user: User, from_date: date, to_date: date):
        return BankingSyncResponse(synced_count=5, new_count=5, sync_id="s_test")


class FakeOnboardingService:
    async def get_progress(self, user: User):
        return OnboardingProgressResponse(
            labeled_count=5,
            required_count=5,
            is_chatbot_unlocked=True,
            next_step=OnboardingNextStep.READY,
        )

    async def create_first_insight(self, user: User):
        return FirstInsightResponse(
            headline="당신은 지속 소비에 쓸 때 만족도가 높네요",
            supporting_data=FirstInsightSupportingData(category="지속 소비", avg_score=4.6, count=5),
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
                category="LASTING",
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
                    category="LASTING",
                    occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                    score=5,
                    text="오래 입을 수 있어서 좋음",
                )
            ],
        )


class FakeChatbotService:
    async def start_session(self, user: User, request):
        return CreateChatbotSessionResponse(
            session_id="sess_test",
            websocket_url="/v1/ws/chatbot/sess_test",
            started_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            model_tier=ChatbotModelTier.FULL,
        )

    async def decide_session(self, user_id: str, session_id: str, decision: ChatbotDecision):
        return DecideChatbotSessionResponse(
            session_id=session_id,
            decision=decision,
            summary=ChatbotSummary(
                product="에어팟",
                amount=350000,
                user_reasoning="자주 사용",
                ai_data_shown="만족도 비교",
                decision=decision,
            ),
            linked_transaction_id=None,
        )

    async def list_sessions(self, **kwargs):
        return ChatbotSessionListResponse(sessions=[], next_cursor=None)


class FakeRetrospectiveService:
    async def submit_retrospective(self, user: User, request):
        return SubmitRetrospectiveResponse(
            retrospective_id="r_test",
            week_start=request.week_start,
            completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
            submitted_count=len(request.answers),
            weekly_insight=WeeklyInsight(headline="이번 주 만족도 평균 4.0점", highlight="지속 소비"),
        )

    async def get_weekly_summary(self, user: User, retrospective_id: str):
        return WeeklySummaryResponse(
            retrospective_id=retrospective_id,
            week_start=date(2026, 4, 20),
            week_end=date(2026, 4, 26),
            spending_comparison=SpendingComparison(
                current_amount=200000,
                previous_amount=350000,
                difference_amount=-150000,
                difference_percent=-42.9,
                difference_display="-150000",
                difference_percent_display="-42.9%",
                saved_amount=150000,
            ),
            saved_amount_comparison=AmountComparison(
                current_amount=350000,
                previous_amount=0,
                difference_amount=350000,
                difference_percent=None,
                difference_display="+350000",
                difference_percent_display="N/A",
            ),
            top_happy_consumption=TopHappyConsumption(
                message="tester님의 행복 소비는 지속 소비 지출입니다.",
                category="LASTING",
                category_name="지속 소비",
                avg_score=4.0,
                total_amount=200000,
                count=1,
            ),
            happy_purchase_archive=[],
        )


class FakeInsightService:
    async def get_happy_purchases(self, **kwargs):
        return HappyPurchasesResponse(items=[], total_count=0, total_amount=0, next_cursor=None)

    async def get_saved_amount(self, **kwargs):
        return SavedAmountResponse(total_saved=350000, skip_count=1, reconsider_count=0, recent_skips=[])


class FakeSubscriptionService:
    async def get_status(self, user: User):
        return SubscriptionStatusResponse(
            tier=SubscriptionTier.FREE_FULL,
            chatbot_usage_count=1,
            chatbot_full_remaining=4,
            downgrades_at=None,
            next_billing_date=None,
        )


class EmptyTransactionService:
    async def list_transactions(self, **kwargs):
        return TransactionListResponse(
            transactions=[],
            next_cursor=None,
            spending_comparison=MonthlySpendingComparison(
                current_month_amount=0,
                previous_month_amount=0,
                difference_amount=0,
                difference_percent=None,
                difference_display="0",
                difference_percent_display="N/A",
            ),
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
        chatbot_usage_count=1,
    )


def install_journey_overrides(app: FastAPI) -> None:
    from app.core.deps import get_transaction_service

    app.dependency_overrides[get_auth_service] = FakeAuthService
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_banking_service] = FakeBankingService
    app.dependency_overrides[get_onboarding_service] = FakeOnboardingService
    app.dependency_overrides[get_chatbot_service] = FakeChatbotService
    app.dependency_overrides[get_retrospective_service] = FakeRetrospectiveService
    app.dependency_overrides[get_insight_service] = FakeInsightService
    app.dependency_overrides[get_subscription_service] = FakeSubscriptionService
    app.dependency_overrides[get_transaction_service] = EmptyTransactionService


def test_new_user_core_journey(app: FastAPI, client: TestClient):
    install_journey_overrides(app)

    signup = client.post(
        "/v1/auth/signup",
        json={"email": "user@example.com", "password": "password123", "nickname": "tester"},
    )
    assert signup.status_code == 201
    assert signup.json()["data"]["access_token"] == "access-token"

    oauth = client.post("/v1/banking/oauth/start", json={"provider": "OPEN_BANKING_KR"})
    assert oauth.status_code == 200

    sync = client.post("/v1/banking/sync", json={"from_date": "2026-04-20", "to_date": "2026-04-26"})
    assert sync.json()["data"]["new_count"] == 5

    progress = client.get("/v1/onboarding/progress")
    assert progress.json()["data"]["is_chatbot_unlocked"] is True

    onboarding_feedback = client.post(
        "/v1/onboarding/feedback",
        json={
            "answers": [
                {"question_id": "oq_t_1", "transaction_id": "t_1", "score": 5, "text": "오래 입을 수 있어서 좋음"}
            ]
        },
    )
    assert onboarding_feedback.json()["data"]["happy_purchase_archive"][0]["transaction_id"] == "t_1"

    chatbot = client.post("/v1/chatbot/sessions", json={"initial_message": "에어팟 살까?"})
    assert chatbot.json()["data"]["session_id"] == "sess_test"

    decision = client.post("/v1/chatbot/sessions/sess_test/decide", json={"decision": "SKIP"})
    assert decision.json()["data"]["summary"]["amount"] == 350000

    retrospective = client.post(
        "/v1/retrospectives",
        json={
            "week_start": "2026-04-20",
            "answers": [{"question_id": "rq_t_1", "transaction_id": "t_1", "score": 4, "text": "좋음"}],
        },
    )
    assert retrospective.json()["data"]["retrospective_id"] == "r_test"
    assert "spending_comparison" not in retrospective.json()["data"]

    weekly_summary = client.get("/v1/retrospectives/r_test/weekly-summary")
    assert weekly_summary.json()["data"]["spending_comparison"]["saved_amount"] == 150000

    saved_amount = client.get("/v1/insights/saved-amount")
    assert saved_amount.json()["data"]["total_saved"] == 350000

    subscription = client.get("/v1/subscription")
    assert subscription.json()["data"]["chatbot_full_remaining"] == 4
