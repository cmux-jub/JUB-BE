import json
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


@dataclass(frozen=True)
class QuestionCandidate:
    question_id: str
    amount: int
    merchant: str
    category: str
    occurred_at: str
    selection_reason: str
    merchant_count: int = 1
    linked_user_reasoning: str | None = None
    category_avg_score: float | None = None


@dataclass(frozen=True)
class GeneratedQuestion:
    question_id: str
    pattern_summary: str
    title: str
    body: str
    min_label: str
    max_label: str


class SpendingQuestionGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, candidates: list[QuestionCandidate]) -> list[GeneratedQuestion]:
        if not candidates:
            return []
        if not self.settings.openai_api_key:
            return [self.create_fallback_question(candidate) for candidate in candidates]

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
                        "max_tokens": 1200,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "소비 회고 질문 생성기입니다. 각 후보 거래마다 한국어 질문을 만듭니다. "
                                    "죄책감이나 지시형 표현은 피하고, "
                                    "1~5점 만족도와 선택 메모로 답할 수 있게 만듭니다. "
                                    "반드시 JSON만 출력합니다."
                                ),
                            },
                            {"role": "user", "content": self.build_prompt(candidates)},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()

            text = payload["choices"][0]["message"]["content"]
            return self.parse_response(text, candidates)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return [self.create_fallback_question(candidate) for candidate in candidates]

    @staticmethod
    def build_prompt(candidates: list[QuestionCandidate]) -> str:
        return json.dumps(
            {
                "instructions": {
                    "output": (
                        '{"questions":[{"question_id":"...","pattern_summary":"...",'
                        '"title":"...","body":"...","min_label":"아쉬웠어요","max_label":"만족스러웠어요"}]}'
                    )
                },
                "candidates": [candidate.__dict__ for candidate in candidates],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def parse_response(text: str, candidates: list[QuestionCandidate]) -> list[GeneratedQuestion]:
        payload = json.loads(text)
        raw_questions = payload.get("questions", [])
        questions_by_id = {
            question.get("question_id"): question for question in raw_questions if isinstance(question, dict)
        }
        generated: list[GeneratedQuestion] = []
        for candidate in candidates:
            question = questions_by_id.get(candidate.question_id)
            if question is None:
                generated.append(SpendingQuestionGenerator.create_fallback_question(candidate))
                continue
            generated.append(
                GeneratedQuestion(
                    question_id=candidate.question_id,
                    pattern_summary=str(question.get("pattern_summary") or ""),
                    title=str(question.get("title") or ""),
                    body=str(question.get("body") or ""),
                    min_label=str(question.get("min_label") or "아쉬웠어요"),
                    max_label=str(question.get("max_label") or "만족스러웠어요"),
                )
            )
        return generated

    @staticmethod
    def create_fallback_question(candidate: QuestionCandidate) -> GeneratedQuestion:
        formatted_amount = f"{candidate.amount:,}원"
        if candidate.selection_reason in {"CHATBOT_FOLLOW_UP"}:
            reasoning = ""
            if candidate.linked_user_reasoning:
                reasoning = f" 구매 전에는 '{candidate.linked_user_reasoning}'라고 남겼어요."
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary="구매 전 챗봇 상담과 연결된 소비입니다.",
                title="상담 후 결정한 이 소비는 기대에 가까웠나요?",
                body=(
                    f"{candidate.merchant}에서 쓴 {formatted_amount}이 "
                    f"실제 사용 경험에서도 만족스러웠는지 돌아봐 주세요.{reasoning}"
                ),
                min_label="기대보다 아쉬웠어요",
                max_label="기대만큼 만족했어요",
            )
        if candidate.selection_reason in {"REPEATED_PURCHASE", "REPEATED_MERCHANT"}:
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary=f"{candidate.merchant} 소비가 반복해서 나타났습니다.",
                title="반복된 이 소비는 계속 만족을 주고 있나요?",
                body=(
                    f"이번 기간에 {candidate.merchant} 관련 소비가 "
                    f"{candidate.merchant_count}번 보였어요. 습관처럼 쓴 돈인지, "
                    "여전히 만족스러운 선택인지 평가해 주세요."
                ),
                min_label="습관에 가까웠어요",
                max_label="계속 만족스러웠어요",
            )
        if candidate.selection_reason in {"UNUSUAL_PATTERN", "TIME_PATTERN"}:
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary="평소보다 늦은 시간대의 소비입니다.",
                title="이 시간대의 소비는 나에게 충분히 필요했나요?",
                body=(
                    f"{candidate.merchant}에서 쓴 {formatted_amount}을 다시 보면, "
                    "그 순간의 필요와 만족이 균형을 이뤘는지 알려주세요."
                ),
                min_label="아쉬움이 남아요",
                max_label="필요한 소비였어요",
            )
        if candidate.selection_reason in {"HIGH_UNCERTAINTY"}:
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary="카테고리 분류 신뢰도가 낮아 직접 확인이 필요한 소비입니다.",
                title="이 소비는 어떤 의미의 소비로 기억되나요?",
                body=(
                    f"{candidate.merchant}의 {formatted_amount} 소비가 즉시 즐거움, "
                    "오래 남는 가치, 필수 지출 중 어디에 가까웠는지 "
                    "만족도와 함께 남겨주세요."
                ),
                min_label="애매했어요",
                max_label="의미가 분명했어요",
            )
        if candidate.selection_reason in {"HIGH_SATISFACTION_REINFORCE"}:
            avg = ""
            if candidate.category_avg_score:
                avg = f" 과거 비슷한 카테고리 평균 만족도는 {candidate.category_avg_score:.1f}점입니다."
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary="이전에 만족도가 높았던 소비 패턴과 비슷합니다.",
                title="이번에도 만족도가 높았던 소비였나요?",
                body=(
                    f"{candidate.merchant}에서 쓴 {formatted_amount}이 "
                    f"이전의 좋은 소비 경험과 이어졌는지 확인해 주세요.{avg}"
                ),
                min_label="이번엔 덜했어요",
                max_label="이번에도 좋았어요",
            )
        if candidate.selection_reason in {"LARGE_AMOUNT", "LARGE_AMOUNT_GAP"}:
            return GeneratedQuestion(
                question_id=candidate.question_id,
                pattern_summary="기간 내 큰 지출에 해당하는 소비입니다.",
                title="큰 금액이었던 이 소비는 다시 봐도 만족스러웠나요?",
                body=(
                    f"{candidate.merchant}에서 쓴 {formatted_amount}이 "
                    "금액만큼의 만족이나 효용을 남겼는지 1~5점으로 평가해 주세요."
                ),
                min_label="금액 대비 아쉬웠어요",
                max_label="충분히 만족했어요",
            )
        return GeneratedQuestion(
            question_id=candidate.question_id,
            pattern_summary="이번 기간 소비 패턴을 대표하는 항목입니다.",
            title="이번 소비는 한 주를 돌아봤을 때 만족스러웠나요?",
            body=f"{candidate.merchant}에서 쓴 {formatted_amount}이 나에게 남긴 만족도를 기록해 주세요.",
            min_label="아쉬웠어요",
            max_label="만족스러웠어요",
        )
