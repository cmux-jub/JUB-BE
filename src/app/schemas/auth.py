from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import OnboardingStatus, SubscriptionTier


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", maxsplit=1)[-1]:
            raise ValueError("올바른 이메일 형식이 아닙니다")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    onboarding_status: OnboardingStatus


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class UserMeResponse(BaseModel):
    user_id: str
    email: str
    nickname: str
    onboarding_status: OnboardingStatus
    subscription_tier: SubscriptionTier
    chatbot_usage_count: int
    created_at: datetime
