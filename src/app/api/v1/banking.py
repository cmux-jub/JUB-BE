from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_banking_service, get_current_user
from app.models.user import User
from app.schemas.banking import (
    BankingSyncRequest,
    BankingSyncResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthStartRequest,
    OAuthStartResponse,
)
from app.schemas.common import ApiResponse
from app.services.banking_service import BankingService

router = APIRouter(prefix="/banking", tags=["banking"])


@router.post("/oauth/start", response_model=ApiResponse[OAuthStartResponse])
async def start_oauth(
    request: OAuthStartRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[BankingService, Depends(get_banking_service)],
) -> ApiResponse[OAuthStartResponse]:
    result = service.start_oauth(request.provider)
    return ApiResponse(success=True, data=result)


@router.post("/oauth/callback", response_model=ApiResponse[OAuthCallbackResponse])
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[BankingService, Depends(get_banking_service)],
) -> ApiResponse[OAuthCallbackResponse]:
    result = service.handle_callback(request.code, request.state_token)
    return ApiResponse(success=True, data=result)


@router.post("/sync", response_model=ApiResponse[BankingSyncResponse])
async def sync_transactions(
    request: BankingSyncRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[BankingService, Depends(get_banking_service)],
) -> ApiResponse[BankingSyncResponse]:
    result = await service.sync_transactions(current_user, request.from_date, request.to_date)
    return ApiResponse(success=True, data=result)
