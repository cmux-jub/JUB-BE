from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_retrospective_service
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.retrospective import (
    CurrentWeekRetrospectiveResponse,
    RetrospectiveHistoryResponse,
    SubmitRetrospectiveRequest,
    SubmitRetrospectiveResponse,
    WeeklySummaryResponse,
)
from app.services.retrospective_service import RetrospectiveService

router = APIRouter(prefix="/retrospectives", tags=["retrospectives"])


@router.get("/current-week", response_model=ApiResponse[CurrentWeekRetrospectiveResponse])
async def get_current_week_retrospective(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RetrospectiveService, Depends(get_retrospective_service)],
) -> ApiResponse[CurrentWeekRetrospectiveResponse]:
    result = await service.get_current_week(current_user)
    return ApiResponse(success=True, data=result)


@router.post("", response_model=ApiResponse[SubmitRetrospectiveResponse])
async def submit_retrospective(
    request: SubmitRetrospectiveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RetrospectiveService, Depends(get_retrospective_service)],
) -> ApiResponse[SubmitRetrospectiveResponse]:
    result = await service.submit_retrospective(current_user, request)
    return ApiResponse(success=True, data=result)


@router.get("/{retrospective_id}/weekly-summary", response_model=ApiResponse[WeeklySummaryResponse])
async def get_weekly_summary(
    retrospective_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RetrospectiveService, Depends(get_retrospective_service)],
) -> ApiResponse[WeeklySummaryResponse]:
    result = await service.get_weekly_summary(current_user, retrospective_id)
    return ApiResponse(success=True, data=result)


@router.get("", response_model=ApiResponse[RetrospectiveHistoryResponse])
async def list_retrospectives(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RetrospectiveService, Depends(get_retrospective_service)],
    from_week: date | None = None,
    to_week: date | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[RetrospectiveHistoryResponse]:
    result = await service.list_retrospectives(
        user_id=current_user.id,
        from_week=from_week,
        to_week=to_week,
        cursor=cursor,
        limit=limit,
    )
    return ApiResponse(success=True, data=result)
