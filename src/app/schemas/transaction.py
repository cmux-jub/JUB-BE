from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import Category


class TransactionSummary(BaseModel):
    transaction_id: str
    amount: int
    merchant: str
    category: Category
    category_confidence: float
    occurred_at: datetime
    satisfaction_score: int | None
    satisfaction_text: str | None
    labeled_at: datetime | None


class MonthlySpendingComparison(BaseModel):
    current_month_amount: int
    previous_month_amount: int
    difference_amount: int
    difference_percent: float | None
    difference_display: str
    difference_percent_display: str


class TransactionListResponse(BaseModel):
    transactions: list[TransactionSummary]
    next_cursor: str | None
    spending_comparison: MonthlySpendingComparison


class TransactionDetailResponse(TransactionSummary):
    merchant_mcc: str | None
    linked_chatbot_session_id: str | None


class UpdateCategoryRequest(BaseModel):
    category: Category


class SatisfactionRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=500)


class SatisfactionResponse(BaseModel):
    transaction_id: str
    score: int
    text: str | None
    labeled_at: datetime
