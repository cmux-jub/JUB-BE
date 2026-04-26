import pytest

from app.ai.classifier import (
    CategoryClassification,
    OpenAICategoryClassifier,
    RuleBasedCategoryClassifier,
    TransactionCategoryClassifier,
)
from app.core.config import Settings
from app.core.enums import Category


class FakeAiClassifier:
    async def classify(self, merchant: str, merchant_mcc: str | None = None, amount: int | None = None):
        return CategoryClassification(Category.IMMEDIATE, 0.72)


def test_rule_based_classifier_detects_immediate_category():
    result = RuleBasedCategoryClassifier().classify("스타벅스 강남점", "5814")

    assert result.category == Category.IMMEDIATE
    assert result.confidence >= 0.7


def test_rule_based_classifier_detects_essential_category():
    result = RuleBasedCategoryClassifier().classify("서울교통공사", "4111")

    assert result.category == Category.ESSENTIAL
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_transaction_classifier_uses_ai_when_rule_confidence_is_low():
    classifier = TransactionCategoryClassifier(ai_classifier=FakeAiClassifier())

    result = await classifier.classify("처음보는상점", None, 30000)

    assert result.category == Category.IMMEDIATE
    assert result.confidence == 0.72


def test_openai_classifier_parses_json_response():
    result = OpenAICategoryClassifier.parse_response('{"category":"ESSENTIAL","confidence":0.83}')

    assert result.category == Category.ESSENTIAL
    assert result.confidence == 0.83


@pytest.mark.asyncio
async def test_openai_classifier_falls_back_without_api_key():
    classifier = OpenAICategoryClassifier(Settings(jwt_secret_key="test-secret", openai_api_key=""))

    result = await classifier.classify("알 수 없는 가맹점", None, 30000)

    assert result.category == Category.LASTING
    assert result.confidence == 0.5
