from datetime import date

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrospective import Retrospective, RetrospectiveEntry


class RetrospectiveRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_week(self, user_id: str, week_start: date) -> Retrospective | None:
        stmt = select(Retrospective).where(Retrospective.user_id == user_id, Retrospective.week_start == week_start)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, retrospective: Retrospective, entries: list[RetrospectiveEntry]) -> Retrospective:
        self.db.add(retrospective)
        await self.db.flush()
        for entry in entries:
            entry.retrospective_id = retrospective.id
        self.db.add_all(entries)
        await self.db.commit()
        await self.db.refresh(retrospective)
        return retrospective

    async def list_by_user(
        self,
        user_id: str,
        from_week: date | None = None,
        to_week: date | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> list[Retrospective]:
        stmt = select(Retrospective).where(Retrospective.user_id == user_id)
        stmt = self.apply_filters(stmt, from_week=from_week, to_week=to_week)
        stmt = await self.apply_cursor(stmt, user_id=user_id, cursor=cursor)
        stmt = stmt.order_by(Retrospective.week_start.desc(), Retrospective.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def apply_filters(
        stmt: Select[tuple[Retrospective]],
        from_week: date | None,
        to_week: date | None,
    ) -> Select[tuple[Retrospective]]:
        if from_week is not None:
            stmt = stmt.where(Retrospective.week_start >= from_week)
        if to_week is not None:
            stmt = stmt.where(Retrospective.week_start <= to_week)
        return stmt

    async def apply_cursor(
        self,
        stmt: Select[tuple[Retrospective]],
        user_id: str,
        cursor: str | None,
    ) -> Select[tuple[Retrospective]]:
        if cursor is None:
            return stmt

        cursor_retrospective = await self.find_by_id(user_id, cursor)
        if cursor_retrospective is None:
            return stmt

        return stmt.where(
            or_(
                Retrospective.week_start < cursor_retrospective.week_start,
                and_(
                    Retrospective.week_start == cursor_retrospective.week_start,
                    Retrospective.id < cursor_retrospective.id,
                ),
            )
        )

    async def find_by_id(self, user_id: str, retrospective_id: str) -> Retrospective | None:
        stmt = select(Retrospective).where(Retrospective.user_id == user_id, Retrospective.id == retrospective_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
