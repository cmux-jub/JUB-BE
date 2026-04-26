from datetime import date, datetime

from pydantic import BaseModel

from app.core.enums import Category
from app.schemas.feedback import AmountComparison, TopHappyConsumption


class HappyPurchaseItem(BaseModel):
    transaction_id: str
    amount: int
    related_total_amount: int
    merchant: str
    category: Category
    occurred_at: datetime
    score: int
    text: str | None


class HappyPurchasesResponse(BaseModel):
    items: list[HappyPurchaseItem]
    total_count: int
    total_amount: int
    next_cursor: str | None


class RecentSkipItem(BaseModel):
    session_id: str
    product: str | None
    amount: int | None
    decided_at: datetime | None


class SavedAmountResponse(BaseModel):
    total_saved: int
    skip_count: int
    reconsider_count: int
    recent_skips: list[RecentSkipItem]


class MainMonthlySpendingResponse(BaseModel):
    current_month_amount: int
    previous_month_amount: int
    difference_amount: int
    difference_percent: float | None
    difference_display: str
    difference_percent_display: str


class MainPageSummaryResponse(BaseModel):
    monthly_spending: MainMonthlySpendingResponse
    saved_amount_comparison: AmountComparison
    top_happy_consumption: TopHappyConsumption
    saved_amount: int
    saved_count: int


class CategorySatisfactionItem(BaseModel):
    name: str
    avg_score: float
    count: int
    total_amount: int


class CategorySatisfactionResponse(BaseModel):
    categories: list[CategorySatisfactionItem]


class ScoreTrendPoint(BaseModel):
    week_start: date
    avg_score: float


class ScoreTrendResponse(BaseModel):
    data_points: list[ScoreTrendPoint]
