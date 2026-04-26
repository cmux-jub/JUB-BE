from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_chatbot_service, get_current_user, get_current_websocket_user
from app.core.enums import ChatbotDecision, ChatbotMessageRole, ChatbotModelTier
from app.models.user import User
from app.schemas.chatbot import (
    ChatbotMessageResponse,
    ChatbotSessionDetailResponse,
    ChatbotSessionListItem,
    ChatbotSessionListResponse,
    ChatbotSummary,
    CreateChatbotSessionResponse,
    DecideChatbotSessionResponse,
)


class FakeChatbotService:
    async def start_session(self, user: User, request):
        return CreateChatbotSessionResponse(
            session_id="sess_test",
            websocket_url="/v1/ws/chatbot/sess_test",
            started_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            model_tier=ChatbotModelTier.FULL,
        )

    async def decide_session(self, user_id: str, session_id: str, decision: ChatbotDecision):
        return DecideChatbotSessionResponse(
            session_id=session_id,
            decision=decision,
            summary=ChatbotSummary(
                product="에어팟",
                amount=350000,
                user_reasoning="자주 사용",
                ai_data_shown="만족도 비교",
                decision=decision,
            ),
            linked_transaction_id=None,
        )

    async def list_sessions(self, **kwargs):
        return ChatbotSessionListResponse(
            sessions=[
                ChatbotSessionListItem(
                    session_id="sess_test",
                    started_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    ended_at=None,
                    summary=None,
                    linked_transaction_id=None,
                )
            ],
            next_cursor=None,
        )

    async def get_session_detail(self, user_id: str, session_id: str):
        return ChatbotSessionDetailResponse(
            session_id=session_id,
            started_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            ended_at=None,
            messages=[
                ChatbotMessageResponse(
                    role=ChatbotMessageRole.USER,
                    content="에어팟 살까?",
                    created_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                )
            ],
            summary=None,
            decision=None,
            linked_transaction_id=None,
        )

    async def stream_assistant_tokens(
        self,
        user: User,
        session_id: str,
        content: str,
    ) -> AsyncGenerator[str, None]:
        yield "지난 "
        yield "패턴"

    async def record_assistant_message(self, user: User, session_id: str, content: str):
        return SimpleNamespace(id="msg_test", content=content, data_references=[])


async def fake_current_user():
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def install_chatbot_overrides(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_current_websocket_user] = fake_current_user
    app.dependency_overrides[get_chatbot_service] = FakeChatbotService


def test_create_chatbot_session_success(app: FastAPI, client: TestClient):
    install_chatbot_overrides(app)

    response = client.post(
        "/v1/chatbot/sessions",
        json={"initial_message": "에어팟 살까?", "amount_hint": 350000, "product_hint": "에어팟"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["session_id"] == "sess_test"
    assert response.json()["data"]["model_tier"] == "FULL"


def test_decide_chatbot_session_success(app: FastAPI, client: TestClient):
    install_chatbot_overrides(app)

    response = client.post("/v1/chatbot/sessions/sess_test/decide", json={"decision": "BUY"})

    assert response.status_code == 200
    assert response.json()["data"]["summary"]["product"] == "에어팟"


def test_list_chatbot_sessions_success(app: FastAPI, client: TestClient):
    install_chatbot_overrides(app)

    response = client.get("/v1/chatbot/sessions")

    assert response.status_code == 200
    assert response.json()["data"]["sessions"][0]["session_id"] == "sess_test"


def test_get_chatbot_session_detail_success(app: FastAPI, client: TestClient):
    install_chatbot_overrides(app)

    response = client.get("/v1/chatbot/sessions/sess_test")

    assert response.status_code == 200
    assert response.json()["data"]["messages"][0]["role"] == "user"


def test_chatbot_websocket_user_message_and_decision(app: FastAPI, client: TestClient):
    install_chatbot_overrides(app)

    with client.websocket_connect("/v1/ws/chatbot/sess_test?token=test") as websocket:
        websocket.send_json({"type": "user_message", "content": "자주 쓸 것 같아"})
        assert websocket.receive_json() == {"type": "assistant_token", "content": "지난 "}
        assert websocket.receive_json() == {"type": "assistant_token", "content": "패턴"}
        done = websocket.receive_json()
        assert done["type"] == "assistant_message_done"
        assert done["message_id"] == "msg_test"
        assert done["full_content"] == "지난 패턴"

        websocket.send_json({"type": "decision", "decision": "BUY"})
        closed = websocket.receive_json()
        assert closed["type"] == "session_closed"
        assert closed["summary"]["decision"] == "BUY"
