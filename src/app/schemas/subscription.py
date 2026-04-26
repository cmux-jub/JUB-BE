from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import SubscriptionPlan, SubscriptionTier


class SubscriptionStatusResponse(BaseModel):
    tier: SubscriptionTier
    chatbot_usage_count: int
    chatbot_full_remaining: int
    downgrades_at: datetime | None
    next_billing_date: datetime | None


class UpgradeSubscriptionRequest(BaseModel):
    plan: SubscriptionPlan
    payment_method_token: str = Field(min_length=1)
