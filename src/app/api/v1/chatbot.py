from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, status
from pydantic import ValidationError

from app.core.deps import get_chatbot_service, get_current_user, get_current_websocket_user
from app.core.enums import ChatbotDecision
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.chatbot import (
    AssistantMessageDonePayload,
    ChatbotSessionDetailResponse,
    ChatbotSessionListResponse,
    CreateChatbotSessionRequest,
    CreateChatbotSessionResponse,
    DecideChatbotSessionRequest,
    DecideChatbotSessionResponse,
)
from app.schemas.common import ApiResponse
from app.services.chatbot_service import ChatbotService

router = APIRouter(tags=["chatbot"])


@router.post(
    "/chatbot/sessions",
    response_model=ApiResponse[CreateChatbotSessionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_chatbot_session(
    request: CreateChatbotSessionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatbotService, Depends(get_chatbot_service)],
) -> ApiResponse[CreateChatbotSessionResponse]:
    result = await service.start_session(current_user, request)
    return ApiResponse(success=True, data=result)


@router.post("/chatbot/sessions/{session_id}/decide", response_model=ApiResponse[DecideChatbotSessionResponse])
async def decide_chatbot_session(
    session_id: str,
    request: DecideChatbotSessionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatbotService, Depends(get_chatbot_service)],
) -> ApiResponse[DecideChatbotSessionResponse]:
    result = await service.decide_session(current_user.id, session_id, request.decision)
    return ApiResponse(success=True, data=result)


@router.get("/chatbot/sessions", response_model=ApiResponse[ChatbotSessionListResponse])
async def list_chatbot_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatbotService, Depends(get_chatbot_service)],
    from_date: date | None = None,
    to_date: date | None = None,
    decision: ChatbotDecision | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[ChatbotSessionListResponse]:
    result = await service.list_sessions(
        user_id=current_user.id,
        from_date=from_date,
        to_date=to_date,
        decision=decision,
        cursor=cursor,
        limit=limit,
    )
    return ApiResponse(success=True, data=result)


@router.get("/chatbot/sessions/{session_id}", response_model=ApiResponse[ChatbotSessionDetailResponse])
async def get_chatbot_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatbotService, Depends(get_chatbot_service)],
) -> ApiResponse[ChatbotSessionDetailResponse]:
    result = await service.get_session_detail(current_user.id, session_id)
    return ApiResponse(success=True, data=result)


@router.websocket("/ws/chatbot/{session_id}")
async def chatbot_websocket(
    websocket: WebSocket,
    session_id: str,
    service: Annotated[ChatbotService, Depends(get_chatbot_service)],
    current_user: Annotated[User, Depends(get_current_websocket_user)],
) -> None:
    await websocket.accept()

    while True:
        payload = await websocket.receive_json()
        message_type = payload.get("type")

        try:
            if message_type == "user_message":
                content = str(payload.get("content", "")).strip()
                if not content:
                    raise AppException("INVALID_INPUT", 400, "메시지 내용이 필요합니다")

                full_content = ""
                async for token in service.stream_assistant_tokens(current_user, session_id, content):
                    full_content += token
                    await websocket.send_json({"type": "assistant_token", "content": token})

                assistant_message = await service.record_assistant_message(current_user, session_id, full_content)
                done_payload = AssistantMessageDonePayload(
                    message_id=assistant_message.id,
                    full_content=assistant_message.content,
                    data_references=assistant_message.data_references,
                )
                await websocket.send_json(done_payload.model_dump())

            elif message_type == "decision":
                decision = ChatbotDecision(str(payload.get("decision")))
                result = await service.decide_session(current_user.id, session_id, decision)
                await websocket.send_json(
                    {
                        "type": "session_closed",
                        "session_id": result.session_id,
                        "decision": result.decision.value,
                        "summary": result.summary.model_dump(mode="json"),
                    }
                )
                await websocket.close()
                return

            else:
                raise AppException("INVALID_INPUT", 400, "지원하지 않는 WebSocket 메시지입니다")

        except (AppException, ValidationError, ValueError) as exc:
            if isinstance(exc, AppException):
                code = exc.code
                message = exc.message
            else:
                code = "INVALID_INPUT"
                message = "요청 형식이 올바르지 않습니다"
            await websocket.send_json({"type": "error", "code": code, "message": message})
