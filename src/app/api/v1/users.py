from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.enums import OnboardingStatus, SubscriptionTier
from app.models.user import User
from app.schemas.auth import UserMeResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserMeResponse])
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> ApiResponse[UserMeResponse]:
    return ApiResponse(
        success=True,
        data=UserMeResponse(
            user_id=current_user.id,
            email=current_user.email,
            nickname=current_user.nickname,
            onboarding_status=OnboardingStatus(current_user.onboarding_status),
            subscription_tier=SubscriptionTier(current_user.subscription_tier),
            chatbot_usage_count=current_user.chatbot_usage_count,
            created_at=current_user.created_at,
        ),
    )
