from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.enums import Category, ChatbotDecision, RetrospectiveSelectionReason


class LinkedChatbotSummary(BaseModel):
    session_id: str
    user_reasoning: str | None
    decision: ChatbotDecision


class RetrospectiveTransactionItem(BaseModel):
    transaction_id: str
    amount: int
    merchant: str
    category: Category
    occurred_at: datetime
    selection_reason: RetrospectiveSelectionReason
    linked_chatbot_summary: LinkedChatbotSummary | None


class CurrentWeekRetrospectiveResponse(BaseModel):
    week_start: date
    week_end: date
    is_completed: bool
    transactions: list[RetrospectiveTransactionItem]


class RetrospectiveEntryRequest(BaseModel):
    transaction_id: str
    score: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=500)


class SubmitRetrospectiveRequest(BaseModel):
    week_start: date
    entries: list[RetrospectiveEntryRequest] = Field(min_length=1)


class WeeklyInsight(BaseModel):
    headline: str
    highlight: str


class SubmitRetrospectiveResponse(BaseModel):
    retrospective_id: str
    week_start: date
    completed_at: datetime
    submitted_count: int
    weekly_insight: WeeklyInsight


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
