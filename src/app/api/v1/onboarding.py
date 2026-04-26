from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_onboarding_service
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.onboarding import FirstInsightResponse, OnboardingProgressResponse, TransactionsToLabelResponse
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/transactions-to-label", response_model=ApiResponse[TransactionsToLabelResponse])
async def get_transactions_to_label(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
    limit: Annotated[int, Query(ge=1, le=30)] = 10,
) -> ApiResponse[TransactionsToLabelResponse]:
    result = await service.get_transactions_to_label(current_user, limit=limit)
    return ApiResponse(success=True, data=result)


@router.get("/progress", response_model=ApiResponse[OnboardingProgressResponse])
async def get_onboarding_progress(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> ApiResponse[OnboardingProgressResponse]:
    result = await service.get_progress(current_user)
    return ApiResponse(success=True, data=result)


@router.post("/first-insight", response_model=ApiResponse[FirstInsightResponse])
async def create_first_insight(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> ApiResponse[FirstInsightResponse]:
    result = await service.create_first_insight(current_user)
    return ApiResponse(success=True, data=result)
