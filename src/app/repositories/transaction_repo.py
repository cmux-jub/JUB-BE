from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Category
from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_id(self, user_id: str, transaction_id: str) -> Transaction | None:
        stmt = select(Transaction).where(Transaction.user_id == user_id, Transaction.id == transaction_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_external_id(self, external_id: str) -> Transaction | None:
        stmt = select(Transaction).where(Transaction.external_id == external_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        category: Category | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        stmt = self.apply_filters(stmt, from_date=from_date, to_date=to_date, category=category)
        stmt = await self.apply_cursor(stmt, user_id=user_id, cursor=cursor)
        stmt = stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: str) -> int:
        stmt = select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_labeled_by_user(self, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == user_id, Transaction.satisfaction_score.is_not(None))
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def sum_amount_between(self, user_id: str, from_date: datetime, to_date: datetime) -> int:
        stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= from_date,
            Transaction.occurred_at <= to_date,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_unlabeled_for_onboarding(
        self,
        user_id: str,
        limit: int,
        since: datetime | None = None,
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.satisfaction_score.is_(None),
                Transaction.category != Category.ESSENTIAL.value,
            )
            .order_by(Transaction.category_confidence.asc(), Transaction.amount.desc(), Transaction.occurred_at.desc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(Transaction.occurred_at >= since)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_labeled_for_insight(self, user_id: str) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.satisfaction_score.is_not(None),
                Transaction.category != Category.ESSENTIAL.value,
            )
            .order_by(Transaction.labeled_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_happy_purchases(self, user_id: str, cursor: str | None = None, limit: int = 20) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.satisfaction_score >= 4,
                Transaction.category != Category.ESSENTIAL.value,
            )
            .order_by(Transaction.labeled_at.desc().nullslast(), Transaction.occurred_at.desc(), Transaction.id.desc())
            .limit(limit)
        )
        stmt = await self.apply_cursor(stmt, user_id=user_id, cursor=cursor)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_labeled_since(self, user_id: str, since: datetime | None = None) -> list[Transaction]:
        stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.satisfaction_score.is_not(None),
            Transaction.category != Category.ESSENTIAL.value,
        )
        if since is not None:
            stmt = stmt.where(Transaction.occurred_at >= since)
        stmt = stmt.order_by(Transaction.occurred_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_retrospective_week(
        self,
        user_id: str,
        week_start: datetime,
        week_end: datetime,
        limit: int,
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.occurred_at >= week_start,
                Transaction.occurred_at <= week_end,
                Transaction.category != Category.ESSENTIAL.value,
            )
            .order_by(
                Transaction.linked_chatbot_session_id.desc().nullslast(),
                Transaction.satisfaction_score.desc().nullslast(),
                Transaction.category_confidence.asc(),
                Transaction.amount.desc(),
                Transaction.occurred_at.desc(),
            )
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_labeled_between(self, user_id: str, from_date: datetime, to_date: datetime) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.occurred_at >= from_date,
                Transaction.occurred_at <= to_date,
                Transaction.satisfaction_score.is_not(None),
            )
            .order_by(Transaction.occurred_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_many(self, transactions: list[Transaction]) -> list[Transaction]:
        self.db.add_all(transactions)
        await self.db.commit()
        for transaction in transactions:
            await self.db.refresh(transaction)
        return transactions

    async def save(self, transaction: Transaction) -> Transaction:
        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    @staticmethod
    def apply_filters(
        stmt: Select[tuple[Transaction]],
        from_date: datetime | None,
        to_date: datetime | None,
        category: Category | None,
    ) -> Select[tuple[Transaction]]:
        if from_date is not None:
            stmt = stmt.where(Transaction.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(Transaction.occurred_at <= to_date)
        if category is not None:
            stmt = stmt.where(Transaction.category == category.value)
        return stmt

    async def apply_cursor(
        self,
        stmt: Select[tuple[Transaction]],
        user_id: str,
        cursor: str | None,
    ) -> Select[tuple[Transaction]]:
        if cursor is None:
            return stmt

        cursor_transaction = await self.find_by_id(user_id, cursor)
        if cursor_transaction is None:
            return stmt

        return stmt.where(
            or_(
                Transaction.occurred_at < cursor_transaction.occurred_at,
                and_(
                    Transaction.occurred_at == cursor_transaction.occurred_at,
                    Transaction.id < cursor_transaction.id,
                ),
            )
        )
