from datetime import UTC, date, datetime

import pytest

from app.core.enums import Category
from app.core.exceptions import AppException
from app.models.transaction import Transaction
from app.services.transaction_service import TransactionService


class FakeTransactionRepository:
    def __init__(self, transactions: list[Transaction]):
        self.transactions = {transaction.id: transaction for transaction in transactions}
        self.list_kwargs = {}

    async def find_by_id(self, user_id: str, transaction_id: str):
        transaction = self.transactions.get(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            return None
        return transaction

    async def list_by_user(self, user_id: str, **kwargs):
        self.list_kwargs = kwargs
        limit = kwargs["limit"]
        transactions = [transaction for transaction in self.transactions.values() if transaction.user_id == user_id]
        transactions.sort(key=lambda transaction: (transaction.occurred_at, transaction.id), reverse=True)
        return transactions[:limit]

    async def sum_amount_between(self, user_id: str, from_date: datetime, to_date: datetime) -> int:
        return sum(
            transaction.amount
            for transaction in self.transactions.values()
            if transaction.user_id == user_id and from_date <= transaction.occurred_at <= to_date
        )

    async def save(self, transaction: Transaction):
        self.transactions[transaction.id] = transaction
        return transaction


def create_transaction(
    transaction_id: str,
    amount: int = 10000,
    merchant: str = "스타벅스",
    occurred_at: datetime | None = None,
) -> Transaction:
    return Transaction(
        id=transaction_id,
        user_id="u_test",
        external_id=f"ext_{transaction_id}",
        account_id="a_test",
        amount=amount,
        merchant=merchant,
        merchant_mcc="5814",
        category=Category.IMMEDIATE.value,
        category_confidence=0.9,
        occurred_at=occurred_at or datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_list_transactions_returns_next_cursor():
    transactions = [
        create_transaction("t_1"),
        create_transaction("t_2"),
        create_transaction("t_3"),
    ]
    service = TransactionService(FakeTransactionRepository(transactions))

    result = await service.list_transactions(user_id="u_test", limit=2)

    assert len(result.transactions) == 2
    assert result.next_cursor == "t_2"
    assert result.spending_comparison.difference_display == "+30000"


@pytest.mark.asyncio
async def test_list_transactions_defaults_to_recent_three_months():
    repo = FakeTransactionRepository([])
    service = TransactionService(repo, today=date(2026, 4, 26))

    await service.list_transactions(user_id="u_test")

    assert repo.list_kwargs["from_date"] == datetime(2026, 1, 26, 0, 0, tzinfo=UTC)
    assert repo.list_kwargs["to_date"] == datetime(2026, 4, 26, 23, 59, 59, 999999, tzinfo=UTC)


@pytest.mark.asyncio
async def test_list_transactions_returns_monthly_spending_increase():
    transactions = [
        create_transaction("t_apr_1", amount=10000, occurred_at=datetime(2026, 4, 3, 12, 0, tzinfo=UTC)),
        create_transaction("t_apr_2", amount=5000, occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC)),
        create_transaction("t_mar_1", amount=12000, occurred_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC)),
    ]
    service = TransactionService(FakeTransactionRepository(transactions), today=date(2026, 4, 26))

    result = await service.list_transactions(user_id="u_test")

    assert result.spending_comparison.current_month_amount == 15000
    assert result.spending_comparison.previous_month_amount == 12000
    assert result.spending_comparison.difference_amount == 3000
    assert result.spending_comparison.difference_display == "+3000"


@pytest.mark.asyncio
async def test_monthly_spending_comparison_formats_decrease():
    transactions = [
        create_transaction("t_apr_1", amount=7000, occurred_at=datetime(2026, 4, 3, 12, 0, tzinfo=UTC)),
        create_transaction("t_mar_1", amount=12000, occurred_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC)),
    ]
    service = TransactionService(FakeTransactionRepository(transactions), today=date(2026, 4, 26))

    result = await service.get_monthly_spending_comparison(user_id="u_test")

    assert result.difference_amount == -5000
    assert result.difference_display == "-5000"


@pytest.mark.asyncio
async def test_get_transaction_returns_detail():
    service = TransactionService(FakeTransactionRepository([create_transaction("t_1")]))

    result = await service.get_transaction("u_test", "t_1")

    assert result.transaction_id == "t_1"
    assert result.merchant_mcc == "5814"


@pytest.mark.asyncio
async def test_update_category_sets_confidence_to_manual_value():
    service = TransactionService(FakeTransactionRepository([create_transaction("t_1")]))

    result = await service.update_category("u_test", "t_1", Category.LASTING)

    assert result.category == Category.LASTING
    assert result.category_confidence == 1.0


@pytest.mark.asyncio
async def test_record_satisfaction_updates_score_and_label_time():
    service = TransactionService(FakeTransactionRepository([create_transaction("t_1")]))

    result = await service.record_satisfaction("u_test", "t_1", 4, "만족")

    assert result.transaction_id == "t_1"
    assert result.score == 4
    assert result.text == "만족"
    assert result.labeled_at is not None


@pytest.mark.asyncio
async def test_get_transaction_raises_not_found():
    service = TransactionService(FakeTransactionRepository([]))

    with pytest.raises(AppException) as exc_info:
        await service.get_transaction("u_test", "missing")

    assert exc_info.value.code == "NOT_FOUND"
