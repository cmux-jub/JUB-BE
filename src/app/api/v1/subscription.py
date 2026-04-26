from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_subscription_service
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.subscription import SubscriptionStatusResponse, UpgradeSubscriptionRequest
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("", response_model=ApiResponse[SubscriptionStatusResponse])
async def get_subscription_status(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> ApiResponse[SubscriptionStatusResponse]:
    result = await service.get_status(current_user)
    return ApiResponse(success=True, data=result)


@router.post("/upgrade", response_model=ApiResponse[SubscriptionStatusResponse])
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> ApiResponse[SubscriptionStatusResponse]:
    result = await service.upgrade(current_user, request)
    return ApiResponse(success=True, data=result)
