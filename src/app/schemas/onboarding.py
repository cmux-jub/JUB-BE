from datetime import datetime

from pydantic import BaseModel

from app.core.enums import Category, OnboardingNextStep, OnboardingSelectionReason


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
