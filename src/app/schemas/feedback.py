from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import Category


class FeedbackTransactionSnapshot(BaseModel):
    transaction_id: str
    amount: int
    merchant: str
    category: Category
    occurred_at: datetime


class ScoreScale(BaseModel):
    min: int = 1
    max: int = 5
    min_label: str
    max_label: str


class FeedbackQuestionContent(BaseModel):
    title: str
    body: str
    answer_type: str = "SCORE_WITH_TEXT"
    score_scale: ScoreScale
    required: bool = True


class FeedbackAnswerRequest(BaseModel):
    question_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    score: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=500)


class HappyArchiveItem(BaseModel):
    transaction_id: str
    amount: int
    related_total_amount: int
    merchant: str
    category: Category
    occurred_at: datetime
    score: int
    text: str | None


class AmountComparison(BaseModel):
    current_amount: int
    previous_amount: int
    difference_amount: int
    difference_percent: float | None
    difference_display: str
    difference_percent_display: str


class SpendingComparison(AmountComparison):
    saved_amount: int


class TopHappyConsumption(BaseModel):
    message: str
    category: Category | None
    category_name: str | None
    avg_score: float | None
    total_amount: int
    count: int
