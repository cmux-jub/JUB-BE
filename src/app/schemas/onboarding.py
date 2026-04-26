from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import Category, OnboardingNextStep, OnboardingSelectionReason
from app.schemas.feedback import (
    FeedbackAnswerRequest,
    FeedbackQuestionContent,
    FeedbackTransactionSnapshot,
    HappyArchiveItem,
    TopHappyConsumption,
)


class OnboardingTransactionItem(BaseModel):
    transaction_id: str
    amount: int
    merchant: str
    category: Category
    occurred_at: datetime
    selection_reason: OnboardingSelectionReason
    question: str


class TransactionsToLabelResponse(BaseModel):
    labeled_count: int
    required_count: int
    transactions: list[OnboardingTransactionItem]


class OnboardingQuestionItem(BaseModel):
    question_id: str
    transaction: FeedbackTransactionSnapshot
    selection_reason: OnboardingSelectionReason
    pattern_summary: str
    question: FeedbackQuestionContent


class OnboardingQuestionsResponse(BaseModel):
    labeled_count: int
    required_count: int
    question_count: int
    min_question_count: int
    max_question_count: int
    questions: list[OnboardingQuestionItem]


class OnboardingProgressResponse(BaseModel):
    labeled_count: int
    required_count: int
    is_chatbot_unlocked: bool
    next_step: OnboardingNextStep


class FirstInsightSupportingData(BaseModel):
    category: str
    avg_score: float
    count: int


class FirstInsightResponse(BaseModel):
    headline: str
    supporting_data: FirstInsightSupportingData


class OnboardingAnswerRequest(FeedbackAnswerRequest):
    pass


class SubmitOnboardingFeedbackRequest(BaseModel):
    answers: list[OnboardingAnswerRequest] = Field(min_length=1, max_length=10)


class SubmitOnboardingFeedbackResponse(BaseModel):
    labeled_count: int
    required_count: int
    is_chatbot_unlocked: bool
    chatbot_context_ready: bool
    first_insight: FirstInsightResponse | None
    top_happy_consumption: TopHappyConsumption
    happy_purchase_archive: list[HappyArchiveItem]
