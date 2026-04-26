from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ChatbotDecision, ChatbotMessageRole, ChatbotModelTier


class CreateChatbotSessionRequest(BaseModel):
    initial_message: str = Field(min_length=1, max_length=1000)
    amount_hint: int | None = Field(default=None, ge=0)
    product_hint: str | None = Field(default=None, max_length=255)


class CreateChatbotSessionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    session_id: str
    websocket_url: str
    started_at: datetime
    model_tier: ChatbotModelTier


class DecideChatbotSessionRequest(BaseModel):
    decision: ChatbotDecision


class ChatbotSummary(BaseModel):
    product: str | None
    amount: int | None
    user_reasoning: str | None
    ai_data_shown: str | None
    decision: ChatbotDecision


class DecideChatbotSessionResponse(BaseModel):
    session_id: str
    decision: ChatbotDecision
    summary: ChatbotSummary
    linked_transaction_id: str | None


class ChatbotSessionListItem(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: datetime | None
    summary: ChatbotSummary | None
    linked_transaction_id: str | None


class ChatbotSessionListResponse(BaseModel):
    sessions: list[ChatbotSessionListItem]
    next_cursor: str | None


class ChatbotMessageResponse(BaseModel):
    role: ChatbotMessageRole
    content: str
    created_at: datetime


class ChatbotSessionDetailResponse(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: datetime | None
    messages: list[ChatbotMessageResponse]
    summary: ChatbotSummary | None
    decision: ChatbotDecision | None
    linked_transaction_id: str | None


class AssistantMessageDonePayload(BaseModel):
    type: str = "assistant_message_done"
    message_id: str
    full_content: str
    data_references: list[dict[str, Any]]
