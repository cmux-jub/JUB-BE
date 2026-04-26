from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.health import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthCheckResponse])
async def health_check() -> ApiResponse[HealthCheckResponse]:
    return ApiResponse(success=True, data=HealthCheckResponse(status="ok"))
