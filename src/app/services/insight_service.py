from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from app.core.enums import (
    Category,
    CategorySatisfactionPeriod,
    ChatbotDecision,
    SavedAmountPeriod,
    ScoreTrendPeriod,
)
from app.models.chatbot import ChatbotSession
from app.models.transaction import Transaction
from app.repositories.chatbot_repo import ChatbotRepository
from app.repositories.retrospective_repo import RetrospectiveRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.insight import (
    CategorySatisfactionItem,
    CategorySatisfactionResponse,
    HappyPurchaseItem,
    HappyPurchasesResponse,
    RecentSkipItem,
    SavedAmountResponse,
    ScoreTrendPoint,
    ScoreTrendResponse,
)

FREE_FULL_CHATBOT_LIMIT = 5
CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


class InsightService:
    def __init__(
        self,
        transaction_repo: TransactionRepository,
        chatbot_repo: ChatbotRepository,
        retrospective_repo: RetrospectiveRepository,
        today: date | None = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.chatbot_repo = chatbot_repo
        self.retrospective_repo = retrospective_repo
        self.today = today

    async def get_happy_purchases(
        self,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> HappyPurchasesResponse:
        normalized_limit = min(max(limit, 1), 100)
        page_items = await self.transaction_repo.list_happy_purchases(
            user_id=user_id,
            cursor=cursor,
            limit=normalized_limit + 1,
        )
        all_labeled = await self.transaction_repo.list_labeled_since(user_id=user_id)
        happy_transactions = [
            transaction
            for transaction in all_labeled
            if transaction.satisfaction_score is not None and transaction.satisfaction_score >= 4
        ]
        has_next = len(page_items) > normalized_limit
        items = page_items[:normalized_limit]

        return HappyPurchasesResponse(
            items=[self.to_happy_purchase_item(transaction) for transaction in items],
            total_count=len(happy_transactions),
            total_amount=sum(transaction.amount for transaction in happy_transactions),
            next_cursor=items[-1].id if has_next and items else None,
        )

    async def get_saved_amount(self, user_id: str, period: SavedAmountPeriod) -> SavedAmountResponse:
        since = self.resolve_saved_amount_since(period)
        sessions = await self.chatbot_repo.list_decided_sessions(
            user_id=user_id,
            decisions=[ChatbotDecision.SKIP, ChatbotDecision.RECONSIDER],
            from_date=since,
            limit=1000,
        )
        skip_sessions = [session for session in sessions if session.decision == ChatbotDecision.SKIP.value]
        reconsider_sessions = [session for session in sessions if session.decision == ChatbotDecision.RECONSIDER.value]

        return SavedAmountResponse(
            total_saved=sum(self.summary_amount(session) or 0 for session in skip_sessions),
            skip_count=len(skip_sessions),
            reconsider_count=len(reconsider_sessions),
            recent_skips=[self.to_recent_skip_item(session) for session in skip_sessions[:5]],
        )

    async def get_category_satisfaction(
        self,
        user_id: str,
        period: CategorySatisfactionPeriod,
    ) -> CategorySatisfactionResponse:
        since = self.resolve_category_since(period)
        transactions = await self.transaction_repo.list_labeled_since(user_id=user_id, since=since)
        scores_by_category: dict[Category, list[int]] = defaultdict(list)
        amount_by_category: dict[Category, int] = defaultdict(int)

        for transaction in transactions:
            if transaction.satisfaction_score is None:
                continue
            category = Category(transaction.category)
            scores_by_category[category].append(transaction.satisfaction_score)
            amount_by_category[category] += transaction.amount

        categories = [
            CategorySatisfactionItem(
                name=CATEGORY_LABELS[category],
                avg_score=round(sum(scores) / len(scores), 1),
                count=len(scores),
                total_amount=amount_by_category[category],
            )
            for category, scores in scores_by_category.items()
        ]
        categories.sort(key=lambda item: (item.avg_score, item.count), reverse=True)
        return CategorySatisfactionResponse(categories=categories)

    async def get_score_trend(self, user_id: str, period: ScoreTrendPeriod) -> ScoreTrendResponse:
        week_count = self.resolve_trend_week_count(period)
        current_week_start = self.resolve_week_start(self.today or datetime.now(UTC).date())
        from_week = current_week_start - timedelta(weeks=week_count - 1)
        retrospectives = await self.retrospective_repo.list_by_user(
            user_id=user_id,
            from_week=from_week,
            to_week=current_week_start,
            limit=week_count + 1,
        )
        sorted_retrospectives = sorted(retrospectives, key=lambda retrospective: retrospective.week_start)
        return ScoreTrendResponse(
            data_points=[
                ScoreTrendPoint(week_start=retrospective.week_start, avg_score=retrospective.avg_score)
                for retrospective in sorted_retrospectives
            ]
        )

    @staticmethod
    def to_happy_purchase_item(transaction: Transaction) -> HappyPurchaseItem:
        return HappyPurchaseItem(
            transaction_id=transaction.id,
            amount=transaction.amount,
            merchant=transaction.merchant,
            category=Category(transaction.category),
            occurred_at=transaction.occurred_at,
            score=transaction.satisfaction_score or 0,
            text=transaction.satisfaction_text,
        )

    @staticmethod
    def to_recent_skip_item(session: ChatbotSession) -> RecentSkipItem:
        return RecentSkipItem(
            session_id=session.id,
            product=session.summary.get("product") if session.summary else session.product_hint,
            amount=InsightService.summary_amount(session),
            decided_at=session.ended_at,
        )

    @staticmethod
    def summary_amount(session: ChatbotSession) -> int | None:
        if session.summary and isinstance(session.summary.get("amount"), int):
            return session.summary["amount"]
        return session.amount_hint

    def resolve_saved_amount_since(self, period: SavedAmountPeriod) -> datetime | None:
        today = self.today or datetime.now(UTC).date()
        if period == SavedAmountPeriod.MONTH:
            return datetime(today.year, today.month, 1, tzinfo=UTC)
        if period == SavedAmountPeriod.YEAR:
            return datetime(today.year, 1, 1, tzinfo=UTC)
        return None

    def resolve_category_since(self, period: CategorySatisfactionPeriod) -> datetime | None:
        today = self.today or datetime.now(UTC).date()
        if period == CategorySatisfactionPeriod.DAYS_30:
            return datetime.combine(today - timedelta(days=30), datetime.min.time(), tzinfo=UTC)
        if period == CategorySatisfactionPeriod.DAYS_90:
            return datetime.combine(today - timedelta(days=90), datetime.min.time(), tzinfo=UTC)
        return None

    @staticmethod
    def resolve_trend_week_count(period: ScoreTrendPeriod) -> int:
        if period == ScoreTrendPeriod.WEEKS_8:
            return 8
        if period == ScoreTrendPeriod.WEEKS_12:
            return 12
        return 26

    @staticmethod
    def resolve_week_start(value: date) -> date:
        return value - timedelta(days=value.weekday())
