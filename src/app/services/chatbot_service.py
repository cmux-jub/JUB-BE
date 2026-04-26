from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, time

from app.ai.chatbot_client import OpenAIChatClient
from app.ai.summarizer import ChatbotSummarizer
from app.core.config import Settings, get_settings
from app.core.enums import (
    Category,
    ChatbotDecision,
    ChatbotMessageRole,
    ChatbotModelTier,
    SubscriptionTier,
)
from app.core.exceptions import AppException, ErrorCode
from app.models.chatbot import ChatbotMessage, ChatbotSession
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.chatbot_repo import ChatbotRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.chatbot import (
    ChatbotMessageResponse,
    ChatbotSessionDetailResponse,
    ChatbotSessionListItem,
    ChatbotSessionListResponse,
    ChatbotSummary,
    CreateChatbotSessionRequest,
    CreateChatbotSessionResponse,
    DecideChatbotSessionResponse,
)
from app.tasks.chatbot_tasks import enqueue_chatbot_summary_task

FREE_FULL_CHATBOT_LIMIT = 5
CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


class ChatbotService:
    def __init__(
        self,
        chatbot_repo: ChatbotRepository,
        user_repo: UserRepository,
        transaction_repo: TransactionRepository,
        chat_client: OpenAIChatClient | None = None,
        summarizer: ChatbotSummarizer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.chatbot_repo = chatbot_repo
        self.user_repo = user_repo
        self.transaction_repo = transaction_repo
        self.chat_client = chat_client or OpenAIChatClient()
        self.summarizer = summarizer or ChatbotSummarizer()
        self.settings = settings or get_settings()

    async def start_session(self, user: User, request: CreateChatbotSessionRequest) -> CreateChatbotSessionResponse:
        model_tier = await self.resolve_model_tier(user)
        session = ChatbotSession(
            user_id=user.id,
            initial_message=request.initial_message,
            amount_hint=request.amount_hint,
            product_hint=request.product_hint,
            model_tier=model_tier.value,
            started_at=datetime.now(UTC),
        )
        created_session = await self.chatbot_repo.create_session(session)
        await self.chatbot_repo.add_message(
            ChatbotMessage(
                session_id=created_session.id,
                role=ChatbotMessageRole.USER.value,
                content=request.initial_message,
                data_references=[],
            )
        )
        await self.increment_usage(user)
        return CreateChatbotSessionResponse(
            session_id=created_session.id,
            websocket_url=f"{self.settings.api_v1_prefix}/ws/chatbot/{created_session.id}",
            started_at=created_session.started_at,
            model_tier=model_tier,
        )

    async def stream_assistant_tokens(
        self,
        user: User,
        session_id: str,
        content: str,
    ) -> AsyncGenerator[str, None]:
        session = await self.get_existing_session(user.id, session_id)
        self.ensure_session_open(session)
        await self.chatbot_repo.add_message(
            ChatbotMessage(
                session_id=session.id,
                role=ChatbotMessageRole.USER.value,
                content=content,
                data_references=[],
            )
        )
        messages = await self.chatbot_repo.list_messages(session.id)
        system_prompt = await self.build_system_prompt(user)

        async for token in self.chat_client.stream_reply(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=ChatbotModelTier(session.model_tier),
        ):
            yield token

    async def record_assistant_message(self, user: User, session_id: str, content: str) -> ChatbotMessage:
        session = await self.get_existing_session(user.id, session_id)
        return await self.chatbot_repo.add_message(
            ChatbotMessage(
                session_id=session.id,
                role=ChatbotMessageRole.ASSISTANT.value,
                content=content,
                data_references=[],
            )
        )

    async def decide_session(
        self,
        user_id: str,
        session_id: str,
        decision: ChatbotDecision,
    ) -> DecideChatbotSessionResponse:
        session = await self.get_existing_session(user_id, session_id)
        messages = await self.chatbot_repo.list_messages(session.id)
        summary = await self.summarizer.summarize(session=session, messages=messages, decision=decision)

        session.decision = decision.value
        session.summary = summary.model_dump(mode="json")
        session.ended_at = datetime.now(UTC)
        saved_session = await self.chatbot_repo.save_session(session)
        enqueue_chatbot_summary_task(saved_session.id)

        return DecideChatbotSessionResponse(
            session_id=saved_session.id,
            decision=decision,
            summary=summary,
            linked_transaction_id=saved_session.linked_transaction_id,
        )

    async def list_sessions(
        self,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        decision: ChatbotDecision | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ChatbotSessionListResponse:
        normalized_limit = min(max(limit, 1), 100)
        sessions = await self.chatbot_repo.list_sessions(
            user_id=user_id,
            from_date=self.start_of_day(from_date),
            to_date=self.end_of_day(to_date),
            decision=decision,
            cursor=cursor,
            limit=normalized_limit + 1,
        )
        has_next = len(sessions) > normalized_limit
        page_items = sessions[:normalized_limit]
        return ChatbotSessionListResponse(
            sessions=[self.to_list_item(session) for session in page_items],
            next_cursor=page_items[-1].id if has_next and page_items else None,
        )

    async def get_session_detail(self, user_id: str, session_id: str) -> ChatbotSessionDetailResponse:
        session = await self.get_existing_session(user_id, session_id)
        messages = await self.chatbot_repo.list_messages(session.id)
        return ChatbotSessionDetailResponse(
            session_id=session.id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            messages=[
                ChatbotMessageResponse(
                    role=ChatbotMessageRole(message.role),
                    content=message.content,
                    created_at=message.created_at,
                )
                for message in messages
            ],
            summary=self.parse_summary(session.summary),
            decision=ChatbotDecision(session.decision) if session.decision else None,
            linked_transaction_id=session.linked_transaction_id,
        )

    async def get_existing_session(self, user_id: str, session_id: str) -> ChatbotSession:
        session = await self.chatbot_repo.find_session(user_id, session_id)
        if session is None:
            raise AppException(ErrorCode.NOT_FOUND, 404, "챗봇 세션을 찾을 수 없습니다")
        return session

    async def resolve_model_tier(self, user: User) -> ChatbotModelTier:
        if user.subscription_tier == SubscriptionTier.PAID.value:
            return ChatbotModelTier.FULL
        if (
            user.chatbot_usage_count < FREE_FULL_CHATBOT_LIMIT
            and user.subscription_tier == SubscriptionTier.FREE_FULL.value
        ):
            return ChatbotModelTier.FULL
        if user.subscription_tier != SubscriptionTier.FREE_LIMITED.value:
            user.subscription_tier = SubscriptionTier.FREE_LIMITED.value
            await self.user_repo.save(user)
        return ChatbotModelTier.LITE

    async def increment_usage(self, user: User) -> None:
        user.chatbot_usage_count += 1
        if (
            user.subscription_tier == SubscriptionTier.FREE_FULL.value
            and user.chatbot_usage_count >= FREE_FULL_CHATBOT_LIMIT
        ):
            user.subscription_tier = SubscriptionTier.FREE_LIMITED.value
        await self.user_repo.save(user)

    async def build_system_prompt(self, user: User) -> str:
        labeled_transactions = await self.transaction_repo.list_labeled_for_insight(user.id)
        if not labeled_transactions:
            context = "- 아직 라벨 데이터가 부족합니다. 일반적인 소비 만족 경향만 조심스럽게 제시하세요."
        else:
            context = self.build_user_context(labeled_transactions)

        return "\n".join(
            [
                "당신은 Aftertaste의 담담한 상담사입니다.",
                "- 공감형 친구처럼 호들갑 떨지 않습니다.",
                "- 데이터 기반으로 사용자의 패턴을 보여줍니다.",
                "- 결정은 사용자가 하며, 구매를 강요하지 않습니다.",
                "[사용자 컨텍스트]",
                context,
            ]
        )

    @staticmethod
    def build_user_context(transactions: list[Transaction]) -> str:
        scores_by_category: dict[Category, list[int]] = {}
        for transaction in transactions:
            if transaction.satisfaction_score is None:
                continue
            category = Category(transaction.category)
            scores_by_category.setdefault(category, []).append(transaction.satisfaction_score)

        lines = []
        for category, scores in sorted(
            scores_by_category.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            reverse=True,
        )[:3]:
            avg_score = sum(scores) / len(scores)
            lines.append(f"- {CATEGORY_LABELS[category]} 평균 만족도: {avg_score:.1f}점 ({len(scores)}건)")
        return "\n".join(lines)

    @staticmethod
    def ensure_session_open(session: ChatbotSession) -> None:
        if session.ended_at is not None:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "이미 종료된 챗봇 세션입니다")

    @staticmethod
    def to_list_item(session: ChatbotSession) -> ChatbotSessionListItem:
        return ChatbotSessionListItem(
            session_id=session.id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            summary=ChatbotService.parse_summary(session.summary),
            linked_transaction_id=session.linked_transaction_id,
        )

    @staticmethod
    def parse_summary(summary: dict | None) -> ChatbotSummary | None:
        if summary is None:
            return None
        return ChatbotSummary(**summary)

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
