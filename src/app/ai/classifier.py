import json
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings
from app.core.enums import Category

AI_CLASSIFICATION_THRESHOLD = 0.7
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


@dataclass(frozen=True)
class CategoryClassification:
    category: Category
    confidence: float


class RuleBasedCategoryClassifier:
    def classify(self, merchant: str, merchant_mcc: str | None = None) -> CategoryClassification:
        normalized_merchant = merchant.lower()
        normalized_mcc = merchant_mcc or ""

        if self.contains_any(normalized_merchant, ["버스", "지하철", "택시", "통신", "전기", "가스", "보험"]):
            return CategoryClassification(Category.ESSENTIAL, 0.9)
        if normalized_mcc in {"4111", "4814", "4900"}:
            return CategoryClassification(Category.ESSENTIAL, 0.9)

        if self.contains_any(normalized_merchant, ["스타벅스", "카페", "배달", "맥도날드", "술집", "편의점"]):
            return CategoryClassification(Category.IMMEDIATE, 0.9)
        if normalized_mcc in {"5812", "5814", "5921", "5499"}:
            return CategoryClassification(Category.IMMEDIATE, 0.85)

        if self.contains_any(normalized_merchant, ["유니클로", "쿠팡", "강의", "서점", "전자", "구독", "애플"]):
            return CategoryClassification(Category.LASTING, 0.85)
        if normalized_mcc in {"5732", "5942", "5651", "8299"}:
            return CategoryClassification(Category.LASTING, 0.8)

        return CategoryClassification(Category.LASTING, 0.5)

    @staticmethod
    def contains_any(value: str, keywords: list[str]) -> bool:
        return any(keyword in value for keyword in keywords)


class OpenAICategoryClassifier:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def classify(
        self,
        merchant: str,
        merchant_mcc: str | None = None,
        amount: int | None = None,
    ) -> CategoryClassification:
        if not self.settings.openai_api_key:
            return CategoryClassification(Category.LASTING, 0.5)

        prompt = (
            "거래 정보를 보고 IMMEDIATE/LASTING/ESSENTIAL 중 하나로 분류하세요. "
            'JSON만 출력하세요. 예: {"category":"IMMEDIATE","confidence":0.8}\n'
            f"merchant={merchant}\nmerchant_mcc={merchant_mcc}\namount={amount}"
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    OPENAI_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openai_background_model,
                        "max_tokens": 120,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "거래 정보를 IMMEDIATE, LASTING, ESSENTIAL 중 하나로 분류하는 분류기입니다. "
                                    "반드시 JSON만 출력합니다."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()

            text = payload["choices"][0]["message"]["content"]
            return self.parse_response(text)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return CategoryClassification(Category.LASTING, 0.5)

    @staticmethod
    def parse_response(text: str) -> CategoryClassification:
        payload = json.loads(text)
        return CategoryClassification(Category(payload["category"]), float(payload["confidence"]))


class TransactionCategoryClassifier:
    def __init__(
        self,
        rule_classifier: RuleBasedCategoryClassifier | None = None,
        ai_classifier: OpenAICategoryClassifier | None = None,
    ) -> None:
        self.rule_classifier = rule_classifier or RuleBasedCategoryClassifier()
        self.ai_classifier = ai_classifier or OpenAICategoryClassifier()

    async def classify(
        self,
        merchant: str,
        merchant_mcc: str | None = None,
        amount: int | None = None,
    ) -> CategoryClassification:
        rule_result = self.rule_classifier.classify(merchant, merchant_mcc)
        if rule_result.confidence >= AI_CLASSIFICATION_THRESHOLD:
            return rule_result

        return await self.ai_classifier.classify(merchant=merchant, merchant_mcc=merchant_mcc, amount=amount)
