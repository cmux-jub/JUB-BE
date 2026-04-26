from datetime import UTC, datetime

import pytest

from app.core.enums import Category, OnboardingNextStep, OnboardingSelectionReason, OnboardingStatus, SubscriptionTier
from app.core.exceptions import AppException
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.onboarding import OnboardingAnswerRequest, SubmitOnboardingFeedbackRequest
from app.services.onboarding_service import OnboardingService


class FakeTransactionRepository:
    def __init__(self, transactions: list[Transaction]):
        self.transactions = transactions

    async def count_labeled_by_user(self, user_id: str):
        return len(
            [
                transaction
                for transaction in self.transactions
                if transaction.user_id == user_id and transaction.satisfaction_score is not None
            ]
        )

    async def count_by_user(self, user_id: str):
        return len([transaction for transaction in self.transactions if transaction.user_id == user_id])

    async def list_unlabeled_for_onboarding(self, user_id: str, limit: int, since=None):
        transactions = [
            transaction
            for transaction in self.transactions
            if transaction.user_id == user_id and transaction.satisfaction_score is None
        ]
        if since is not None:
            transactions = [transaction for transaction in transactions if transaction.occurred_at >= since]
        return transactions[:limit]

    async def list_labeled_for_insight(self, user_id: str):
        return [
            transaction
            for transaction in self.transactions
            if transaction.user_id == user_id and transaction.satisfaction_score is not None
        ]

    async def find_by_id(self, user_id: str, transaction_id: str):
        return next(
            (
                transaction
                for transaction in self.transactions
                if transaction.user_id == user_id and transaction.id == transaction_id
            ),
            None,
        )

    async def save(self, transaction: Transaction):
        return transaction


class FakeUserRepository:
    async def update_onboarding_status(self, user: User, status: OnboardingStatus):
        user.onboarding_status = status.value
        return user


def create_user(status: OnboardingStatus = OnboardingStatus.NEEDS_BANK_LINK) -> User:
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password="hashed",
        nickname="tester",
        birth_year=1998,
        onboarding_status=status.value,
        subscription_tier=SubscriptionTier.FREE_FULL.value,
        chatbot_usage_count=0,
    )


def create_transaction(
    transaction_id: str,
    category: Category,
    score: int | None = None,
    amount: int = 50000,
    confidence: float = 0.9,
    merchant: str = "테스트상점",
) -> Transaction:
    return Transaction(
        id=transaction_id,
        user_id="u_test",
        external_id=f"ext_{transaction_id}",
        account_id="a_test",
        amount=amount,
        merchant=merchant,
        merchant_mcc=None,
        category=category.value,
        category_confidence=confidence,
        occurred_at=datetime(2026, 4, 26, 22, 0, tzinfo=UTC),
        satisfaction_score=score,
        labeled_at=datetime(2026, 4, 26, 23, 0, tzinfo=UTC) if score is not None else None,
    )


@pytest.mark.asyncio
async def test_get_transactions_to_label_returns_curated_questions():
    user = create_user()
    transactions = [
        create_transaction("t_1", Category.LASTING, amount=89000, confidence=0.5, merchant="유니클로"),
        create_transaction("t_2", Category.IMMEDIATE, score=4, merchant="스타벅스"),
    ]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    result = await service.get_transactions_to_label(user, limit=10)

    assert result.labeled_count == 1
    assert result.required_count == 5
    assert result.transactions[0].transaction_id == "t_1"
    assert result.transactions[0].selection_reason == OnboardingSelectionReason.HIGH_UNCERTAINTY
    assert "만족스러우세요" in result.transactions[0].question
    assert user.onboarding_status == OnboardingStatus.NEEDS_LABELING.value


@pytest.mark.asyncio
async def test_get_questions_returns_five_to_ten_ai_feedback_questions():
    user = create_user()
    transactions = [
        create_transaction(f"t_{index}", Category.LASTING, amount=50000 + index, merchant=f"상점{index}")
        for index in range(6)
    ]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    result = await service.get_questions(user, limit=6)

    assert result.question_count == 6
    assert result.min_question_count == 5
    assert result.max_question_count == 10
    assert result.questions[0].question_id == "oq_t_0"
    assert result.questions[0].question.answer_type == "SCORE_WITH_TEXT"


@pytest.mark.asyncio
async def test_get_progress_requires_bank_link_when_no_transactions():
    user = create_user(status=OnboardingStatus.NEEDS_LABELING)
    service = OnboardingService(FakeTransactionRepository([]), FakeUserRepository())

    result = await service.get_progress(user)

    assert result.labeled_count == 0
    assert result.is_chatbot_unlocked is False
    assert result.next_step == OnboardingNextStep.LINK_BANK
    assert user.onboarding_status == OnboardingStatus.NEEDS_BANK_LINK.value


@pytest.mark.asyncio
async def test_get_progress_ready_after_required_labels():
    user = create_user(status=OnboardingStatus.NEEDS_LABELING)
    transactions = [create_transaction(f"t_{index}", Category.LASTING, score=5) for index in range(5)]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    result = await service.get_progress(user)

    assert result.labeled_count == 5
    assert result.is_chatbot_unlocked is True
    assert result.next_step == OnboardingNextStep.READY
    assert user.onboarding_status == OnboardingStatus.READY.value


@pytest.mark.asyncio
async def test_create_first_insight_requires_five_labels():
    user = create_user()
    transactions = [create_transaction("t_1", Category.LASTING, score=5)]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    with pytest.raises(AppException) as exc_info:
        await service.create_first_insight(user)

    assert exc_info.value.code == "LABELING_REQUIRED"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_first_insight_uses_highest_average_category():
    user = create_user(status=OnboardingStatus.NEEDS_LABELING)
    transactions = [
        create_transaction("t_1", Category.LASTING, score=5),
        create_transaction("t_2", Category.LASTING, score=5),
        create_transaction("t_3", Category.IMMEDIATE, score=3),
        create_transaction("t_4", Category.IMMEDIATE, score=4),
        create_transaction("t_5", Category.IMMEDIATE, score=4),
    ]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    result = await service.create_first_insight(user)

    assert result.headline == "당신은 지속 소비에 쓸 때 만족도가 높네요"
    assert result.supporting_data.category == "지속 소비"
    assert result.supporting_data.avg_score == 5.0
    assert result.supporting_data.count == 2
    assert user.onboarding_status == OnboardingStatus.READY.value


@pytest.mark.asyncio
async def test_submit_feedback_updates_answers_and_returns_happy_archive():
    user = create_user(status=OnboardingStatus.NEEDS_LABELING)
    transactions = [create_transaction(f"t_{index}", Category.LASTING) for index in range(5)]
    service = OnboardingService(FakeTransactionRepository(transactions), FakeUserRepository())

    result = await service.submit_feedback(
        user,
        SubmitOnboardingFeedbackRequest(
            answers=[
                OnboardingAnswerRequest(
                    question_id=f"oq_t_{index}",
                    transaction_id=f"t_{index}",
                    score=5,
                    text="좋음",
                )
                for index in range(5)
            ]
        ),
    )

    assert result.is_chatbot_unlocked is True
    assert result.chatbot_context_ready is True
    assert result.top_happy_consumption.message == "tester님의 행복 소비는 지속 소비 지출입니다."
    assert len(result.happy_purchase_archive) == 5
    assert result.happy_purchase_archive[0].related_total_amount == 250000
    assert transactions[0].satisfaction_score == 5
