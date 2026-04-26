from datetime import UTC, date, datetime, time

from app.core.enums import Category, OnboardingStatus
from app.core.exceptions import AppException, ErrorCode
from app.models.transaction import Transaction
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.transaction import (
    MonthlySpendingComparison,
    SatisfactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
    TransactionSummary,
)


class TransactionService:
    def __init__(
        self,
        repo: TransactionRepository,
        user_repo: UserRepository | None = None,
        today: date | None = None,
    ) -> None:
        self.repo = repo
        self.user_repo = user_repo
        self.today = today

    async def list_transactions(
        self,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        category: Category | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> TransactionListResponse:
        normalized_limit = min(max(limit, 1), 100)
        resolved_from_date = from_date or self.default_from_date()
        resolved_to_date = to_date or (self.today or datetime.now(UTC).date())
        transactions = await self.repo.list_by_user(
            user_id=user_id,
            from_date=self.start_of_day(resolved_from_date),
            to_date=self.end_of_day(resolved_to_date),
            category=category,
            cursor=cursor,
            limit=normalized_limit + 1,
        )
        spending_comparison = await self.get_monthly_spending_comparison(user_id)
        has_next = len(transactions) > normalized_limit
        page_items = transactions[:normalized_limit]
        return TransactionListResponse(
            transactions=[self.to_summary(transaction) for transaction in page_items],
            next_cursor=page_items[-1].id if has_next and page_items else None,
            spending_comparison=spending_comparison,
        )

    async def get_transaction(self, user_id: str, transaction_id: str) -> TransactionDetailResponse:
        transaction = await self.get_existing_transaction(user_id, transaction_id)
        return self.to_detail(transaction)

    async def update_category(
        self,
        user_id: str,
        transaction_id: str,
        category: Category,
    ) -> TransactionDetailResponse:
        transaction = await self.get_existing_transaction(user_id, transaction_id)
        transaction.category = category.value
        transaction.category_confidence = 1.0
        saved_transaction = await self.repo.save(transaction)
        return self.to_detail(saved_transaction)

    async def record_satisfaction(
        self,
        user_id: str,
        transaction_id: str,
        score: int,
        text: str | None,
    ) -> SatisfactionResponse:
        transaction = await self.get_existing_transaction(user_id, transaction_id)
        transaction.satisfaction_score = score
        transaction.satisfaction_text = text
        transaction.labeled_at = datetime.now(UTC)
        saved_transaction = await self.repo.save(transaction)
        await self.update_onboarding_status_after_label(user_id)
        return SatisfactionResponse(
            transaction_id=saved_transaction.id,
            score=saved_transaction.satisfaction_score or score,
            text=saved_transaction.satisfaction_text,
            labeled_at=saved_transaction.labeled_at or transaction.labeled_at,
        )

    async def get_existing_transaction(self, user_id: str, transaction_id: str) -> Transaction:
        transaction = await self.repo.find_by_id(user_id, transaction_id)
        if transaction is None:
            raise AppException(ErrorCode.NOT_FOUND, 404, "거래를 찾을 수 없습니다")
        return transaction

    async def update_onboarding_status_after_label(self, user_id: str) -> None:
        if self.user_repo is None:
            return

        user = await self.user_repo.find_by_id(user_id)
        if user is None:
            return

        labeled_count = await self.repo.count_labeled_by_user(user_id)
        if labeled_count >= 5 and user.onboarding_status != OnboardingStatus.READY.value:
            await self.user_repo.update_onboarding_status(user, OnboardingStatus.READY)

    async def get_monthly_spending_comparison(self, user_id: str) -> MonthlySpendingComparison:
        today = self.today or datetime.now(UTC).date()
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start.fromordinal(current_month_start.toordinal() - 1)
        previous_month_start = previous_month_end.replace(day=1)

        current_month_amount = await self.repo.sum_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(current_month_start),
            to_date=self.end_of_day(today),
        )
        previous_month_amount = await self.repo.sum_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(previous_month_start),
            to_date=self.end_of_day(previous_month_end),
        )
        difference_amount = current_month_amount - previous_month_amount
        return MonthlySpendingComparison(
            current_month_amount=current_month_amount,
            previous_month_amount=previous_month_amount,
            difference_amount=difference_amount,
            difference_display=f"{difference_amount:+d}" if difference_amount != 0 else "0",
        )

    @staticmethod
    def to_summary(transaction: Transaction) -> TransactionSummary:
        return TransactionSummary(
            transaction_id=transaction.id,
            amount=transaction.amount,
            merchant=transaction.merchant,
            category=Category(transaction.category),
            category_confidence=transaction.category_confidence,
            occurred_at=transaction.occurred_at,
            satisfaction_score=transaction.satisfaction_score,
            satisfaction_text=transaction.satisfaction_text,
            labeled_at=transaction.labeled_at,
        )

    @classmethod
    def to_detail(cls, transaction: Transaction) -> TransactionDetailResponse:
        summary = cls.to_summary(transaction)
        return TransactionDetailResponse(
            **summary.model_dump(),
            merchant_mcc=transaction.merchant_mcc,
            linked_chatbot_session_id=transaction.linked_chatbot_session_id,
        )

    @staticmethod
    def start_of_day(value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, time.min, tzinfo=UTC)

    @staticmethod
    def end_of_day(value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, time.max, tzinfo=UTC)

    def default_from_date(self) -> date:
        today = self.today or datetime.now(UTC).date()
        return self.subtract_months(today, 3)

    @staticmethod
    def subtract_months(value: date, months: int) -> date:
        month_index = value.month - months
        year = value.year
        while month_index <= 0:
            month_index += 12
            year -= 1

        last_day = TransactionService.last_day_of_month(year, month_index)
        return value.replace(year=year, month=month_index, day=min(value.day, last_day))

    @staticmethod
    def last_day_of_month(year: int, month: int) -> int:
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return next_month.toordinal() - date(year, month, 1).toordinal()
