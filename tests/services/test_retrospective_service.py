from datetime import UTC, date, datetime

import pytest

from app.core.enums import (
    Category,
    ChatbotDecision,
    OnboardingStatus,
    RetrospectiveSelectionReason,
    SubscriptionTier,
)
from app.core.exceptions import AppException
from app.models.chatbot import ChatbotSession
from app.models.retrospective import Retrospective, create_retrospective_id
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.retrospective import RetrospectiveAnswerRequest, SubmitRetrospectiveRequest
from app.services.retrospective_service import RetrospectiveService


class FakeRetrospectiveRepository:
    def __init__(self, retrospectives: list[Retrospective] | None = None) -> None:
        self.retrospectives = retrospectives or []

    async def find_by_week(self, user_id: str, week_start: date):
        return next(
            (
                retrospective
                for retrospective in self.retrospectives
                if retrospective.user_id == user_id and retrospective.week_start == week_start
            ),
            None,
        )

    async def create(self, retrospective: Retrospective, entries):
        if retrospective.id is None:
            retrospective.id = create_retrospective_id()
        self.retrospectives.append(retrospective)
        return retrospective

    async def find_by_id(self, user_id: str, retrospective_id: str):
        return next(
            (
                retrospective
                for retrospective in self.retrospectives
                if retrospective.user_id == user_id and retrospective.id == retrospective_id
            ),
            None,
        )

    async def list_by_user(self, user_id: str, **kwargs):
        retrospectives = [retrospective for retrospective in self.retrospectives if retrospective.user_id == user_id]
        return retrospectives[: kwargs["limit"]]


class FakeTransactionRepository:
    def __init__(self, transactions: list[Transaction], previous_transactions: list[Transaction] | None = None) -> None:
        self.transactions = {transaction.id: transaction for transaction in transactions}
        self.previous_transactions = previous_transactions or []

    async def list_for_retrospective_week(self, user_id: str, **kwargs):
        return [transaction for transaction in self.transactions.values() if transaction.user_id == user_id]

    async def list_labeled_for_insight(self, user_id: str):
        return [
            transaction
            for transaction in [*self.transactions.values(), *self.previous_transactions]
            if transaction.user_id == user_id and transaction.satisfaction_score is not None
        ]

    async def list_labeled_since(self, user_id: str, since=None):
        transactions = await self.list_labeled_for_insight(user_id)
        if since is not None:
            transactions = [transaction for transaction in transactions if transaction.occurred_at >= since]
        return transactions

    async def find_by_id(self, user_id: str, transaction_id: str):
        transaction = self.transactions.get(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            return None
        return transaction

    async def save(self, transaction: Transaction):
        self.transactions[transaction.id] = transaction
        return transaction

    async def list_labeled_between(self, user_id: str, from_date, to_date):
        all_transactions = [*self.transactions.values(), *self.previous_transactions]
        return [
            transaction
            for transaction in all_transactions
            if transaction.user_id == user_id
            and transaction.satisfaction_score is not None
            and from_date <= transaction.occurred_at <= to_date
        ]

    async def sum_amount_between(self, user_id: str, from_date, to_date):
        return sum(
            transaction.amount
            for transaction in [*self.transactions.values(), *self.previous_transactions]
            if transaction.user_id == user_id and from_date <= transaction.occurred_at <= to_date
        )


class FakeChatbotRepository:
    def __init__(self, sessions: list[ChatbotSession] | None = None) -> None:
        self.sessions = sessions or []

    async def find_sessions_by_ids(self, user_id: str, session_ids: list[str]):
        return [session for session in self.sessions if session.user_id == user_id and session.id in session_ids]

    async def find_sessions_by_linked_transaction_ids(self, user_id: str, transaction_ids: list[str]):
        return [
            session
            for session in self.sessions
            if session.user_id == user_id and session.linked_transaction_id in transaction_ids
        ]

    async def list_decided_sessions(self, user_id: str, decisions, from_date=None, to_date=None, limit: int = 100):
        sessions = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.decision in {decision.value for decision in decisions}
        ]
        if from_date is not None:
            sessions = [
                session for session in sessions if session.ended_at is not None and session.ended_at >= from_date
            ]
        if to_date is not None:
            sessions = [session for session in sessions if session.ended_at is not None and session.ended_at <= to_date]
        return sessions[:limit]


def create_user() -> User:
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


def create_transaction(
    transaction_id: str,
    category: Category = Category.LASTING,
    amount: int = 50000,
    score: int | None = None,
    confidence: float = 0.9,
    linked_chatbot_session_id: str | None = None,
    occurred_at: datetime | None = None,
) -> Transaction:
    return Transaction(
        id=transaction_id,
        user_id="u_test",
        external_id=f"ext_{transaction_id}",
        account_id="a_test",
        amount=amount,
        merchant="테스트상점",
        merchant_mcc=None,
        category=category.value,
        category_confidence=confidence,
        occurred_at=occurred_at or datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
        satisfaction_score=score,
        linked_chatbot_session_id=linked_chatbot_session_id,
    )


def create_service(
    transactions: list[Transaction],
    sessions: list[ChatbotSession] | None = None,
    retrospectives: list[Retrospective] | None = None,
    previous_transactions: list[Transaction] | None = None,
) -> RetrospectiveService:
    return RetrospectiveService(
        retrospective_repo=FakeRetrospectiveRepository(retrospectives),
        transaction_repo=FakeTransactionRepository(transactions, previous_transactions),
        chatbot_repo=FakeChatbotRepository(sessions),
        today=date(2026, 4, 26),
    )


@pytest.mark.asyncio
async def test_get_current_week_returns_curated_transactions_with_chatbot_summary():
    transaction = create_transaction("t_1", linked_chatbot_session_id="sess_1")
    session = ChatbotSession(
        id="sess_1",
        user_id="u_test",
        initial_message="에어팟 살까?",
        model_tier="FULL",
        decision=ChatbotDecision.BUY.value,
        summary={"user_reasoning": "자주 사용", "decision": "BUY"},
    )
    service = create_service([transaction], [session])

    result = await service.get_current_week(create_user())

    assert result.week_start == date(2026, 4, 20)
    assert result.week_end == date(2026, 4, 26)
    assert result.is_completed is False
    assert result.questions[0].question_id == "rq_t_1"
    assert result.questions[0].selection_reason == RetrospectiveSelectionReason.CHATBOT_FOLLOW_UP
    assert result.questions[0].linked_chatbot_summary.session_id == "sess_1"


@pytest.mark.asyncio
async def test_get_current_week_marks_completed_when_retrospective_exists():
    retrospective = Retrospective(
        id="r_1",
        user_id="u_test",
        week_start=date(2026, 4, 20),
        week_end=date(2026, 4, 26),
        completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
        avg_score=4.0,
        entry_count=1,
        weekly_insight={"headline": "좋아요", "highlight": "지속 소비"},
    )
    service = create_service([create_transaction("t_1")], retrospectives=[retrospective])

    result = await service.get_current_week(create_user())

    assert result.is_completed is True


@pytest.mark.asyncio
async def test_submit_retrospective_updates_transactions_and_creates_insight():
    transaction = create_transaction("t_1", category=Category.LASTING)
    previous = create_transaction(
        "t_prev",
        category=Category.LASTING,
        amount=70000,
        score=3,
        occurred_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )
    service = create_service([transaction], previous_transactions=[previous])

    result = await service.submit_retrospective(
        create_user(),
        SubmitRetrospectiveRequest(
            week_start=date(2026, 4, 20),
            answers=[
                RetrospectiveAnswerRequest(
                    question_id="rq_t_1",
                    transaction_id="t_1",
                    score=5,
                    text="잘 씀",
                )
            ],
        ),
    )

    assert result.retrospective_id.startswith("r_")
    assert result.submitted_count == 1
    assert result.weekly_insight.headline == "이번 주 만족도 평균 5.0점, 지난주보다 +2.0"
    assert result.weekly_insight.highlight == "지속 소비 카테고리에서 가장 높은 만족"
    assert not hasattr(result, "spending_comparison") or "spending_comparison" not in result.model_fields
    assert transaction.satisfaction_score == 5
    assert transaction.satisfaction_text == "잘 씀"


@pytest.mark.asyncio
async def test_submit_retrospective_rejects_unknown_transaction():
    service = create_service([])

    with pytest.raises(AppException) as exc_info:
        await service.submit_retrospective(
            create_user(),
            SubmitRetrospectiveRequest(
                week_start=date(2026, 4, 20),
                answers=[
                    RetrospectiveAnswerRequest(
                        question_id="rq_missing",
                        transaction_id="missing",
                        score=4,
                        text=None,
                    )
                ],
            ),
        )

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_retrospectives_returns_history_with_next_cursor():
    retrospectives = [
        Retrospective(
            id=f"r_{index}",
            user_id="u_test",
            week_start=date(2026, 4, 20 - index * 7),
            week_end=date(2026, 4, 26 - index * 7),
            completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
            avg_score=4.0,
            entry_count=2,
            weekly_insight={"headline": "좋아요", "highlight": "지속 소비"},
        )
        for index in range(3)
    ]
    service = create_service([], retrospectives=retrospectives)

    result = await service.list_retrospectives("u_test", limit=2)

    assert len(result.retrospectives) == 2
    assert result.next_cursor == "r_1"


@pytest.mark.asyncio
async def test_get_weekly_summary_returns_spending_and_archive():
    transaction = create_transaction("t_1", category=Category.LASTING, score=5)
    previous = create_transaction(
        "t_prev",
        category=Category.LASTING,
        amount=70000,
        score=3,
        occurred_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )
    retrospective = Retrospective(
        id="r_1",
        user_id="u_test",
        week_start=date(2026, 4, 20),
        week_end=date(2026, 4, 26),
        completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
        avg_score=5.0,
        entry_count=1,
        weekly_insight={"headline": "좋아요", "highlight": "지속 소비"},
    )
    service = create_service([transaction], retrospectives=[retrospective], previous_transactions=[previous])

    result = await service.get_weekly_summary(create_user(), "r_1")

    assert result.retrospective_id == "r_1"
    assert result.week_start == date(2026, 4, 20)
    assert result.week_end == date(2026, 4, 26)
    assert result.spending_comparison.previous_amount == 70000
    assert result.top_happy_consumption.message == "tester님의 행복 소비는 지속 소비 지출입니다."
    assert result.happy_purchase_archive[0].transaction_id == "t_1"


@pytest.mark.asyncio
async def test_get_weekly_summary_not_found():
    service = create_service([])

    with pytest.raises(AppException) as exc_info:
        await service.get_weekly_summary(create_user(), "r_nonexistent")

    assert exc_info.value.code == "NOT_FOUND"
