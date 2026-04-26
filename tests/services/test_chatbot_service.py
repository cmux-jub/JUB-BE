from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.core.enums import (
    ChatbotDecision,
    ChatbotMessageRole,
    ChatbotModelTier,
    OnboardingStatus,
    SubscriptionTier,
)
from app.models.chatbot import ChatbotMessage, ChatbotSession, create_chatbot_message_id, create_chatbot_session_id
from app.models.user import User
from app.schemas.chatbot import ChatbotSummary, CreateChatbotSessionRequest
from app.services.chatbot_service import ChatbotService


class FakeChatbotRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatbotSession] = {}
        self.messages: list[ChatbotMessage] = []

    async def create_session(self, session: ChatbotSession):
        if session.id is None:
            session.id = create_chatbot_session_id()
        self.sessions[session.id] = session
        return session

    async def find_session(self, user_id: str, session_id: str):
        session = self.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    async def list_sessions(self, user_id: str, **kwargs):
        return [session for session in self.sessions.values() if session.user_id == user_id][: kwargs["limit"]]

    async def add_message(self, message: ChatbotMessage):
        if message.id is None:
            message.id = create_chatbot_message_id()
        if message.created_at is None:
            message.created_at = datetime.now(UTC)
        self.messages.append(message)
        return message

    async def list_messages(self, session_id: str):
        return [message for message in self.messages if message.session_id == session_id]

    async def save_session(self, session: ChatbotSession):
        self.sessions[session.id] = session
        return session


class FakeUserRepository:
    async def save(self, user: User):
        return user


class FakeTransactionRepository:
    async def list_labeled_for_insight(self, user_id: str):
        return []


class FakeChatClient:
    async def stream_reply(
        self,
        system_prompt: str,
        messages: list[ChatbotMessage],
        model_tier: ChatbotModelTier,
    ) -> AsyncGenerator[str, None]:
        yield "지난 "
        yield "패턴입니다."


class FakeSummarizer:
    async def summarize(self, session: ChatbotSession, messages: list[ChatbotMessage], decision: ChatbotDecision):
        return ChatbotSummary(
            product=session.product_hint,
            amount=session.amount_hint,
            user_reasoning=messages[-1].content,
            ai_data_shown="패턴 안내",
            decision=decision,
        )


def create_user(chatbot_usage_count: int = 0, tier: SubscriptionTier = SubscriptionTier.FREE_FULL) -> User:
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password="hashed",
        nickname="tester",
        birth_year=1998,
        onboarding_status=OnboardingStatus.READY.value,
        subscription_tier=tier.value,
        chatbot_usage_count=chatbot_usage_count,
    )


def create_service(repo: FakeChatbotRepository | None = None) -> ChatbotService:
    return ChatbotService(
        chatbot_repo=repo or FakeChatbotRepository(),
        user_repo=FakeUserRepository(),
        transaction_repo=FakeTransactionRepository(),
        chat_client=FakeChatClient(),
        summarizer=FakeSummarizer(),
        settings=Settings(api_v1_prefix="/v1", jwt_secret_key="test-secret"),
    )


@pytest.mark.asyncio
async def test_start_session_creates_session_and_initial_message():
    repo = FakeChatbotRepository()
    user = create_user()
    service = create_service(repo)

    result = await service.start_session(
        user,
        CreateChatbotSessionRequest(
            initial_message="에어팟 살까?",
            amount_hint=350000,
            product_hint="에어팟",
        ),
    )

    assert result.session_id.startswith("sess_")
    assert result.websocket_url == f"/v1/ws/chatbot/{result.session_id}"
    assert result.model_tier == ChatbotModelTier.FULL
    assert user.chatbot_usage_count == 1
    assert repo.messages[0].role == ChatbotMessageRole.USER.value


@pytest.mark.asyncio
async def test_start_session_downgrades_after_free_full_limit():
    user = create_user(chatbot_usage_count=5)
    service = create_service()

    result = await service.start_session(user, CreateChatbotSessionRequest(initial_message="고민 중"))

    assert result.model_tier == ChatbotModelTier.LITE
    assert user.subscription_tier == SubscriptionTier.FREE_LIMITED.value


@pytest.mark.asyncio
async def test_stream_assistant_tokens_records_user_message():
    repo = FakeChatbotRepository()
    service = create_service(repo)
    user = create_user()
    session = ChatbotSession(
        id="sess_test",
        user_id=user.id,
        initial_message="처음",
        model_tier=ChatbotModelTier.FULL.value,
    )
    repo.sessions[session.id] = session

    tokens = [token async for token in service.stream_assistant_tokens(user, "sess_test", "추가 질문")]

    assert tokens == ["지난 ", "패턴입니다."]
    assert repo.messages[0].content == "추가 질문"


@pytest.mark.asyncio
async def test_decide_session_closes_session_with_summary():
    repo = FakeChatbotRepository()
    service = create_service(repo)
    user = create_user()
    session = ChatbotSession(
        id="sess_test",
        user_id=user.id,
        initial_message="에어팟 살까?",
        amount_hint=350000,
        product_hint="에어팟",
        model_tier=ChatbotModelTier.FULL.value,
    )
    repo.sessions[session.id] = session
    await repo.add_message(
        ChatbotMessage(
            session_id=session.id,
            role="user",
            content="자주 쓸 것 같아",
            data_references=[],
        )
    )

    result = await service.decide_session(user.id, session.id, ChatbotDecision.BUY)

    assert result.decision == ChatbotDecision.BUY
    assert result.summary.product == "에어팟"
    assert repo.sessions[session.id].ended_at is not None
