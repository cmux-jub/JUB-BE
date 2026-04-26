from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.enums import ChatbotDecision, RetrospectiveSelectionReason
from app.schemas.feedback import (
    AmountComparison,
    FeedbackAnswerRequest,
    FeedbackQuestionContent,
    FeedbackTransactionSnapshot,
    HappyArchiveItem,
    SpendingComparison,
    TopHappyConsumption,
)


class LinkedChatbotSummary(BaseModel):
    session_id: str
    user_reasoning: str | None
    decision: ChatbotDecision


class RetrospectiveQuestionItem(BaseModel):
    question_id: str
    transaction: FeedbackTransactionSnapshot
    selection_reason: RetrospectiveSelectionReason
    pattern_summary: str
    question: FeedbackQuestionContent
    linked_chatbot_summary: LinkedChatbotSummary | None


class CurrentWeekRetrospectiveResponse(BaseModel):
    week_start: date
    week_end: date
    is_completed: bool
    question_count: int
    min_question_count: int
    max_question_count: int
    questions: list[RetrospectiveQuestionItem]


class RetrospectiveAnswerRequest(FeedbackAnswerRequest):
    pass


class SubmitRetrospectiveRequest(BaseModel):
    week_start: date
    answers: list[RetrospectiveAnswerRequest] = Field(min_length=1, max_length=10)


class WeeklyInsight(BaseModel):
    headline: str
    highlight: str


class SubmitRetrospectiveResponse(BaseModel):
    retrospective_id: str
    week_start: date
    completed_at: datetime
    submitted_count: int
    weekly_insight: WeeklyInsight


class WeeklySummaryResponse(BaseModel):
    retrospective_id: str
    week_start: date
    week_end: date
    spending_comparison: SpendingComparison
    saved_amount_comparison: AmountComparison
    top_happy_consumption: TopHappyConsumption
    happy_purchase_archive: list[HappyArchiveItem]


class RetrospectiveHistoryItem(BaseModel):
    retrospective_id: str
    week_start: date
    week_end: date
    completed_at: datetime
    avg_score: float
    entry_count: int


class RetrospectiveHistoryResponse(BaseModel):
    retrospectives: list[RetrospectiveHistoryItem]
    next_cursor: str | None
