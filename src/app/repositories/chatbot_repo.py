from datetime import datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChatbotDecision
from app.models.chatbot import ChatbotMessage, ChatbotSession


class ChatbotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(self, session: ChatbotSession) -> ChatbotSession:
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def find_session(self, user_id: str, session_id: str) -> ChatbotSession | None:
        stmt = select(ChatbotSession).where(ChatbotSession.user_id == user_id, ChatbotSession.id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_sessions_by_ids(self, user_id: str, session_ids: list[str]) -> list[ChatbotSession]:
        if not session_ids:
            return []
        stmt = select(ChatbotSession).where(ChatbotSession.user_id == user_id, ChatbotSession.id.in_(session_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_sessions_by_linked_transaction_ids(
        self,
        user_id: str,
        transaction_ids: list[str],
    ) -> list[ChatbotSession]:
        if not transaction_ids:
            return []
        stmt = select(ChatbotSession).where(
            ChatbotSession.user_id == user_id,
            ChatbotSession.linked_transaction_id.in_(transaction_ids),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_sessions(
        self,
        user_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        decision: ChatbotDecision | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> list[ChatbotSession]:
        stmt = select(ChatbotSession).where(ChatbotSession.user_id == user_id)
        stmt = self.apply_filters(stmt, from_date=from_date, to_date=to_date, decision=decision)
        stmt = await self.apply_cursor(stmt, user_id=user_id, cursor=cursor)
        stmt = stmt.order_by(ChatbotSession.started_at.desc(), ChatbotSession.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_decided_sessions(
        self,
        user_id: str,
        decisions: list[ChatbotDecision],
        from_date: datetime | None = None,
        limit: int = 100,
    ) -> list[ChatbotSession]:
        stmt = select(ChatbotSession).where(
            ChatbotSession.user_id == user_id,
            ChatbotSession.decision.in_([decision.value for decision in decisions]),
        )
        if from_date is not None:
            stmt = stmt.where(ChatbotSession.ended_at >= from_date)
        stmt = stmt.order_by(ChatbotSession.ended_at.desc().nullslast(), ChatbotSession.started_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_message(self, message: ChatbotMessage) -> ChatbotMessage:
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def list_messages(self, session_id: str) -> list[ChatbotMessage]:
        stmt = (
            select(ChatbotMessage)
            .where(ChatbotMessage.session_id == session_id)
            .order_by(ChatbotMessage.created_at.asc(), ChatbotMessage.id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save_session(self, session: ChatbotSession) -> ChatbotSession:
        await self.db.commit()
        await self.db.refresh(session)
        return session

    @staticmethod
    def apply_filters(
        stmt: Select[tuple[ChatbotSession]],
        from_date: datetime | None,
        to_date: datetime | None,
        decision: ChatbotDecision | None,
    ) -> Select[tuple[ChatbotSession]]:
        if from_date is not None:
            stmt = stmt.where(ChatbotSession.started_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(ChatbotSession.started_at <= to_date)
        if decision is not None:
            stmt = stmt.where(ChatbotSession.decision == decision.value)
        return stmt

    async def apply_cursor(
        self,
        stmt: Select[tuple[ChatbotSession]],
        user_id: str,
        cursor: str | None,
    ) -> Select[tuple[ChatbotSession]]:
        if cursor is None:
            return stmt

        cursor_session = await self.find_session(user_id, cursor)
        if cursor_session is None:
            return stmt

        return stmt.where(
            or_(
                ChatbotSession.started_at < cursor_session.started_at,
                and_(
                    ChatbotSession.started_at == cursor_session.started_at,
                    ChatbotSession.id < cursor_session.id,
                ),
            )
        )
