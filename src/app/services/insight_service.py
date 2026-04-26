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
    MainMonthlySpendingResponse,
    MainPageSummaryResponse,
    RecentSkipItem,
    SavedAmountResponse,
    ScoreTrendPoint,
    ScoreTrendResponse,
)
from app.services.spending_summary import build_spending_comparison, build_top_happy_consumption

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

    async def get_main_summary(self, user_id: str, nickname: str | None = None) -> MainPageSummaryResponse:
        today = self.today or datetime.now(UTC).date()
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        current_month_amount = await self.transaction_repo.sum_amount_between(
            user_id=user_id,
            from_date=datetime.combine(current_month_start, datetime.min.time(), tzinfo=UTC),
            to_date=datetime.combine(today, datetime.max.time(), tzinfo=UTC),
        )
        previous_month_amount = await self.transaction_repo.sum_amount_between(
            user_id=user_id,
            from_date=datetime.combine(previous_month_start, datetime.min.time(), tzinfo=UTC),
            to_date=datetime.combine(previous_month_end, datetime.max.time(), tzinfo=UTC),
        )
        comparison = build_spending_comparison(current_month_amount, previous_month_amount)
        current_month_saved_amount = await self.sum_saved_amount_between(
            user_id=user_id,
            from_date=datetime.combine(current_month_start, datetime.min.time(), tzinfo=UTC),
            to_date=datetime.combine(today, datetime.max.time(), tzinfo=UTC),
        )
        previous_month_saved_amount = await self.sum_saved_amount_between(
            user_id=user_id,
            from_date=datetime.combine(previous_month_start, datetime.min.time(), tzinfo=UTC),
            to_date=datetime.combine(previous_month_end, datetime.max.time(), tzinfo=UTC),
        )
        saved_amount_comparison = build_spending_comparison(current_month_saved_amount, previous_month_saved_amount)
        saved_amount = await self.get_saved_amount(user_id=user_id, period=SavedAmountPeriod.ALL)
        labeled_transactions = await self.transaction_repo.list_labeled_since(user_id=user_id)
        return MainPageSummaryResponse(
            monthly_spending=MainMonthlySpendingResponse(
                current_month_amount=current_month_amount,
                previous_month_amount=previous_month_amount,
                difference_amount=comparison.difference_amount,
                difference_percent=comparison.difference_percent,
                difference_display=comparison.difference_display,
                difference_percent_display=comparison.difference_percent_display,
            ),
            saved_amount_comparison=saved_amount_comparison,
            top_happy_consumption=build_top_happy_consumption(labeled_transactions, nickname=nickname),
            saved_amount=saved_amount.total_saved,
            saved_count=saved_amount.skip_count,
        )

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

        related_total_by_category = self.total_amount_by_category(happy_transactions)
        return HappyPurchasesResponse(
            items=[
                self.to_happy_purchase_item(
                    transaction,
                    related_total_amount=related_total_by_category[Category(transaction.category)],
                )
                for transaction in items
            ],
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

    async def sum_saved_amount_between(self, user_id: str, from_date: datetime, to_date: datetime) -> int:
        sessions = await self.chatbot_repo.list_decided_sessions(
            user_id=user_id,
            decisions=[ChatbotDecision.SKIP],
            from_date=from_date,
            to_date=to_date,
            limit=1000,
        )
        return sum(self.summary_amount(session) or 0 for session in sessions)

    @staticmethod
    def to_happy_purchase_item(transaction: Transaction, related_total_amount: int) -> HappyPurchaseItem:
        return HappyPurchaseItem(
            transaction_id=transaction.id,
            amount=transaction.amount,
            related_total_amount=related_total_amount,
            merchant=transaction.merchant,
            category=Category(transaction.category),
            occurred_at=transaction.occurred_at,
            score=transaction.satisfaction_score or 0,
            text=transaction.satisfaction_text,
        )

    @staticmethod
    def total_amount_by_category(transactions: list[Transaction]) -> dict[Category, int]:
        amount_by_category: dict[Category, int] = defaultdict(int)
        for transaction in transactions:
            amount_by_category[Category(transaction.category)] += transaction.amount
        return amount_by_category

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
