from datetime import UTC, date, datetime

import pytest

from app.core.enums import (
    Category,
    CategorySatisfactionPeriod,
    ChatbotDecision,
    SavedAmountPeriod,
    ScoreTrendPeriod,
)
from app.models.chatbot import ChatbotSession
from app.models.retrospective import Retrospective
from app.models.transaction import Transaction
from app.services.insight_service import InsightService


class FakeTransactionRepository:
    def __init__(self, transactions: list[Transaction]) -> None:
        self.transactions = transactions

    async def list_happy_purchases(self, user_id: str, cursor: str | None = None, limit: int = 20):
        transactions = [
            transaction
            for transaction in self.transactions
            if transaction.user_id == user_id
            and transaction.satisfaction_score is not None
            and transaction.satisfaction_score >= 4
        ]
        return transactions[:limit]

    async def list_labeled_since(self, user_id: str, since=None):
        transactions = [
            transaction
            for transaction in self.transactions
            if transaction.user_id == user_id and transaction.satisfaction_score is not None
        ]
        if since is not None:
            transactions = [transaction for transaction in transactions if transaction.occurred_at >= since]
        return transactions

    async def sum_amount_between(self, user_id: str, from_date: datetime, to_date: datetime) -> int:
        return sum(
            transaction.amount
            for transaction in self.transactions
            if transaction.user_id == user_id and from_date <= transaction.occurred_at <= to_date
        )


class FakeChatbotRepository:
    def __init__(self, sessions: list[ChatbotSession]) -> None:
        self.sessions = sessions

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


class FakeRetrospectiveRepository:
    def __init__(self, retrospectives: list[Retrospective]) -> None:
        self.retrospectives = retrospectives

    async def list_by_user(self, user_id: str, **kwargs):
        from_week = kwargs.get("from_week")
        retrospectives = [retrospective for retrospective in self.retrospectives if retrospective.user_id == user_id]
        if from_week is not None:
            retrospectives = [
                retrospective for retrospective in retrospectives if retrospective.week_start >= from_week
            ]
        return retrospectives[: kwargs["limit"]]


def create_transaction(
    transaction_id: str,
    category: Category,
    score: int,
    amount: int,
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
        category_confidence=0.9,
        occurred_at=occurred_at or datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        satisfaction_score=score,
        satisfaction_text="만족",
    )


def create_service(
    transactions: list[Transaction] | None = None,
    sessions: list[ChatbotSession] | None = None,
    retrospectives: list[Retrospective] | None = None,
) -> InsightService:
    return InsightService(
        transaction_repo=FakeTransactionRepository(transactions or []),
        chatbot_repo=FakeChatbotRepository(sessions or []),
        retrospective_repo=FakeRetrospectiveRepository(retrospectives or []),
        today=date(2026, 4, 26),
    )


@pytest.mark.asyncio
async def test_get_happy_purchases_returns_totals_and_items():
    service = create_service(
        transactions=[
            create_transaction("t_1", Category.IMMEDIATE, 5, 10000),
            create_transaction("t_2", Category.LASTING, 4, 20000),
            create_transaction("t_3", Category.LASTING, 3, 30000),
        ]
    )

    result = await service.get_happy_purchases("u_test", limit=2)

    assert len(result.items) == 2
    assert result.total_count == 2
    assert result.total_amount == 30000
    assert result.items[0].related_total_amount == 10000


@pytest.mark.asyncio
async def test_get_saved_amount_sums_skip_decisions():
    sessions = [
        ChatbotSession(
            id="sess_skip",
            user_id="u_test",
            initial_message="맥북 살까?",
            amount_hint=1500000,
            model_tier="FULL",
            decision=ChatbotDecision.SKIP.value,
            summary={"product": "맥북", "amount": 1500000, "decision": "SKIP"},
            ended_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        ),
        ChatbotSession(
            id="sess_reconsider",
            user_id="u_test",
            initial_message="코트 살까?",
            amount_hint=200000,
            model_tier="FULL",
            decision=ChatbotDecision.RECONSIDER.value,
            summary={"product": "코트", "amount": 200000, "decision": "RECONSIDER"},
            ended_at=datetime(2026, 4, 12, 12, 0, tzinfo=UTC),
        ),
    ]
    service = create_service(sessions=sessions)

    result = await service.get_saved_amount("u_test", SavedAmountPeriod.ALL)

    assert result.total_saved == 1500000
    assert result.skip_count == 1
    assert result.reconsider_count == 1
    assert result.recent_skips[0].product == "맥북"


@pytest.mark.asyncio
async def test_get_main_summary_returns_monthly_spending_and_saved_amount():
    sessions = [
        ChatbotSession(
            id="sess_skip",
            user_id="u_test",
            initial_message="맥북 살까?",
            amount_hint=1500000,
            model_tier="FULL",
            decision=ChatbotDecision.SKIP.value,
            summary={"product": "맥북", "amount": 1500000, "decision": "SKIP"},
            ended_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        )
    ]
    service = create_service(
        transactions=[
            create_transaction("t_apr", Category.LASTING, 4, 100000, datetime(2026, 4, 20, 12, 0, tzinfo=UTC)),
            create_transaction("t_mar", Category.LASTING, 4, 200000, datetime(2026, 3, 20, 12, 0, tzinfo=UTC)),
        ],
        sessions=sessions,
    )

    result = await service.get_main_summary("u_test", nickname="tester")

    assert result.monthly_spending.current_month_amount == 100000
    assert result.monthly_spending.previous_month_amount == 200000
    assert result.monthly_spending.difference_percent_display == "-50.0%"
    assert result.saved_amount_comparison.current_amount == 1500000
    assert result.saved_amount_comparison.previous_amount == 0
    assert result.top_happy_consumption.message == "tester님의 행복 소비는 지속 소비 지출입니다."
    assert result.saved_amount == 1500000
    assert result.saved_count == 1


@pytest.mark.asyncio
async def test_get_category_satisfaction_groups_labeled_transactions():
    service = create_service(
        transactions=[
            create_transaction("t_1", Category.IMMEDIATE, 5, 10000),
            create_transaction("t_2", Category.IMMEDIATE, 3, 20000),
            create_transaction("t_3", Category.LASTING, 5, 30000),
        ]
    )

    result = await service.get_category_satisfaction("u_test", CategorySatisfactionPeriod.ALL)

    assert result.categories[0].name == "지속 소비"
    assert result.categories[0].avg_score == 5.0
    assert result.categories[0].total_amount == 30000


@pytest.mark.asyncio
async def test_get_score_trend_returns_sorted_points():
    retrospectives = [
        Retrospective(
            id="r_2",
            user_id="u_test",
            week_start=date(2026, 4, 20),
            week_end=date(2026, 4, 26),
            completed_at=datetime(2026, 4, 26, 20, 0, tzinfo=UTC),
            avg_score=4.2,
            entry_count=3,
            weekly_insight={"headline": "좋아요", "highlight": "지속 소비"},
        ),
        Retrospective(
            id="r_1",
            user_id="u_test",
            week_start=date(2026, 4, 13),
            week_end=date(2026, 4, 19),
            completed_at=datetime(2026, 4, 19, 20, 0, tzinfo=UTC),
            avg_score=3.8,
            entry_count=2,
            weekly_insight={"headline": "좋아요", "highlight": "즉시 소비"},
        ),
    ]
    service = create_service(retrospectives=retrospectives)

    result = await service.get_score_trend("u_test", ScoreTrendPeriod.WEEKS_8)

    assert [point.week_start for point in result.data_points] == [date(2026, 4, 13), date(2026, 4, 20)]
