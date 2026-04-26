from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_insight_service
from app.core.enums import CategorySatisfactionPeriod, SavedAmountPeriod, ScoreTrendPeriod
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.insight import (
    CategorySatisfactionResponse,
    HappyPurchasesResponse,
    MainPageSummaryResponse,
    SavedAmountResponse,
    ScoreTrendResponse,
)
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/main", response_model=ApiResponse[MainPageSummaryResponse])
async def get_main_page_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InsightService, Depends(get_insight_service)],
) -> ApiResponse[MainPageSummaryResponse]:
    result = await service.get_main_summary(user_id=current_user.id, nickname=current_user.nickname)
    return ApiResponse(success=True, data=result)


@router.get("/happy-purchases", response_model=ApiResponse[HappyPurchasesResponse])
async def get_happy_purchases(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InsightService, Depends(get_insight_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> ApiResponse[HappyPurchasesResponse]:
    result = await service.get_happy_purchases(user_id=current_user.id, limit=limit, cursor=cursor)
    return ApiResponse(success=True, data=result)


@router.get("/saved-amount", response_model=ApiResponse[SavedAmountResponse])
async def get_saved_amount(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InsightService, Depends(get_insight_service)],
    period: SavedAmountPeriod = SavedAmountPeriod.ALL,
) -> ApiResponse[SavedAmountResponse]:
    result = await service.get_saved_amount(user_id=current_user.id, period=period)
    return ApiResponse(success=True, data=result)


@router.get("/category-satisfaction", response_model=ApiResponse[CategorySatisfactionResponse])
async def get_category_satisfaction(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InsightService, Depends(get_insight_service)],
    period: CategorySatisfactionPeriod = CategorySatisfactionPeriod.DAYS_30,
) -> ApiResponse[CategorySatisfactionResponse]:
    result = await service.get_category_satisfaction(user_id=current_user.id, period=period)
    return ApiResponse(success=True, data=result)


@router.get("/score-trend", response_model=ApiResponse[ScoreTrendResponse])
async def get_score_trend(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InsightService, Depends(get_insight_service)],
    period: ScoreTrendPeriod = ScoreTrendPeriod.WEEKS_8,
) -> ApiResponse[ScoreTrendResponse]:
    result = await service.get_score_trend(user_id=current_user.id, period=period)
    return ApiResponse(success=True, data=result)
