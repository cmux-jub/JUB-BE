import json

import httpx

from app.core.config import Settings, get_settings
from app.core.enums import ChatbotDecision
from app.models.chatbot import ChatbotMessage, ChatbotSession
from app.schemas.chatbot import ChatbotSummary

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class ChatbotSummarizer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def summarize(
        self,
        session: ChatbotSession,
        messages: list[ChatbotMessage],
        decision: ChatbotDecision,
    ) -> ChatbotSummary:
        if not self.settings.openai_api_key:
            return self.create_fallback_summary(session, messages, decision)

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    OPENAI_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openai_background_model,
                        "max_tokens": 300,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "다음 챗봇 상담 대화를 product, amount, user_reasoning, ai_data_shown, decision "
                                    "필드로 요약하세요. JSON만 출력합니다."
                                ),
                            },
                            {
                                "role": "user",
                                "content": self.build_summary_input(
                                    session=session,
                                    messages=messages,
                                    decision=decision,
                                ),
                            },
                        ],
                    },
                )
                response.raise_for_status()
                response_payload = response.json()

            payload = json.loads(response_payload["choices"][0]["message"]["content"])
            return ChatbotSummary(
                product=payload.get("product"),
                amount=payload.get("amount"),
                user_reasoning=payload.get("user_reasoning"),
                ai_data_shown=payload.get("ai_data_shown"),
                decision=decision,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self.create_fallback_summary(session, messages, decision)

    @staticmethod
    def create_fallback_summary(
        session: ChatbotSession,
        messages: list[ChatbotMessage],
        decision: ChatbotDecision,
    ) -> ChatbotSummary:
        user_messages = [message.content for message in messages if message.role == "user"]
        assistant_messages = [message.content for message in messages if message.role == "assistant"]
        return ChatbotSummary(
            product=session.product_hint,
            amount=session.amount_hint,
            user_reasoning=user_messages[-1] if user_messages else session.initial_message,
            ai_data_shown=assistant_messages[-1][:120] if assistant_messages else "소비 패턴 기반 상담",
            decision=decision,
        )

    @staticmethod
    def build_summary_input(
        session: ChatbotSession,
        messages: list[ChatbotMessage],
        decision: ChatbotDecision,
    ) -> str:
        lines = [
            f"상품 힌트: {session.product_hint}",
            f"금액 힌트: {session.amount_hint}",
            f"결정: {decision.value}",
            "대화:",
        ]
        lines.extend(f"{message.role}: {message.content}" for message in messages)
        return "\n".join(lines)
