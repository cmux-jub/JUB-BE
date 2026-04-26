import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import Settings, get_settings
from app.core.enums import ChatbotModelTier
from app.models.chatbot import ChatbotMessage

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIChatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def stream_reply(
        self,
        system_prompt: str,
        messages: list[ChatbotMessage],
        model_tier: ChatbotModelTier,
    ) -> AsyncGenerator[str, None]:
        if not self.settings.openai_api_key:
            async for token in self.stream_fallback_reply(messages):
                yield token
            return

        model = (
            self.settings.openai_chat_full_model
            if model_tier == ChatbotModelTier.FULL
            else self.settings.openai_chat_lite_model
        )
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        )

        try:
            async with (
                httpx.AsyncClient(timeout=30) as client,
                client.stream(
                    "POST",
                    OPENAI_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 500,
                        "stream": True,
                        "messages": openai_messages,
                    },
                ) as response,
            ):
                response.raise_for_status()
                async for token in self.iter_stream_tokens(response):
                    yield token
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError):
            async for token in self.stream_fallback_reply(messages):
                yield token

    @staticmethod
    async def iter_stream_tokens(response: httpx.Response) -> AsyncGenerator[str, None]:
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue

            data = line.removeprefix("data: ").strip()
            if data == "[DONE]":
                break

            payload = json.loads(data)
            content = payload["choices"][0].get("delta", {}).get("content")
            if content:
                yield content

    @staticmethod
    async def stream_fallback_reply(messages: list[ChatbotMessage]) -> AsyncGenerator[str, None]:
        last_user_message = next((message.content for message in reversed(messages) if message.role == "user"), "")
        reply = (
            "지난 패턴을 기준으로 보면, 이 소비가 자주 쓰일 물건인지와 "
            "비슷한 금액대에서 만족도가 높았던 선택인지가 핵심입니다. "
            f"지금 고민하신 내용은 '{last_user_message}'로 기록해둘게요."
        )
        for token in reply.split(" "):
            yield f"{token} "
