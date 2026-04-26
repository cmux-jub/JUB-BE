from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_transaction_service
from app.core.enums import Category
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.transaction import (
    SatisfactionRequest,
    SatisfactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
    UpdateCategoryRequest,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=ApiResponse[TransactionListResponse])
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
    from_date: date | None = None,
    to_date: date | None = None,
    category: Category | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[TransactionListResponse]:
    result = await service.list_transactions(
        user_id=current_user.id,
        from_date=from_date,
        to_date=to_date,
        category=category,
        cursor=cursor,
        limit=limit,
    )
    return ApiResponse(success=True, data=result)


@router.get("/{transaction_id}", response_model=ApiResponse[TransactionDetailResponse])
async def get_transaction(
    transaction_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
) -> ApiResponse[TransactionDetailResponse]:
    result = await service.get_transaction(current_user.id, transaction_id)
    return ApiResponse(success=True, data=result)


@router.patch("/{transaction_id}/category", response_model=ApiResponse[TransactionDetailResponse])
async def update_transaction_category(
    transaction_id: str,
    request: UpdateCategoryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
) -> ApiResponse[TransactionDetailResponse]:
    result = await service.update_category(current_user.id, transaction_id, request.category)
    return ApiResponse(success=True, data=result)


@router.post("/{transaction_id}/satisfaction", response_model=ApiResponse[SatisfactionResponse])
async def record_transaction_satisfaction(
    transaction_id: str,
    request: SatisfactionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
) -> ApiResponse[SatisfactionResponse]:
    result = await service.record_satisfaction(
        user_id=current_user.id,
        transaction_id=transaction_id,
        score=request.score,
        text=request.text,
    )
    return ApiResponse(success=True, data=result)
