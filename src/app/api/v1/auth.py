from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import get_auth_service
from app.schemas.auth import AuthTokenResponse, LoginRequest, RefreshTokenRequest, SignupRequest, TokenRefreshResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=ApiResponse[AuthTokenResponse], status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[AuthTokenResponse]:
    result = await service.signup(request)
    return ApiResponse(success=True, data=result)


@router.post("/login", response_model=ApiResponse[AuthTokenResponse])
async def login(
    request: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[AuthTokenResponse]:
    result = await service.login(request)
    return ApiResponse(success=True, data=result)


@router.post("/refresh", response_model=ApiResponse[TokenRefreshResponse])
async def refresh_token(
    request: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenRefreshResponse]:
    result = await service.refresh(request)
    return ApiResponse(success=True, data=result)
