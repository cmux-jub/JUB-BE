from app.core.config import Settings, get_settings
from app.core.enums import OnboardingStatus
from app.core.exceptions import AppException, ErrorCode
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import AuthTokenResponse, LoginRequest, RefreshTokenRequest, SignupRequest, TokenRefreshResponse


class AuthService:
    def __init__(self, repo: UserRepository, settings: Settings | None = None) -> None:
        self.repo = repo
        self.settings = settings or get_settings()

    async def signup(self, request: SignupRequest) -> AuthTokenResponse:
        existing_user = await self.repo.find_by_email(request.email)
        if existing_user is not None:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "이미 가입된 이메일입니다")

        user = User(
            email=request.email,
            hashed_password=hash_password(request.password),
            nickname=request.nickname,
            onboarding_status=OnboardingStatus.NEEDS_BANK_LINK.value,
        )
        created_user = await self.repo.create(user)
        return self.create_auth_response(created_user)

    async def login(self, request: LoginRequest) -> AuthTokenResponse:
        user = await self.repo.find_by_email(request.email)
        if user is None or not verify_password(request.password, user.hashed_password):
            raise AppException(ErrorCode.UNAUTHORIZED, 401, "이메일 또는 비밀번호가 올바르지 않습니다")

        return self.create_auth_response(user)

    async def refresh(self, request: RefreshTokenRequest) -> TokenRefreshResponse:
        user_id = decode_token(request.refresh_token, expected_type="refresh", settings=self.settings)
        user = await self.repo.find_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHORIZED, 401, "인증 정보를 확인할 수 없습니다")

        return TokenRefreshResponse(
            access_token=create_access_token(user.id, settings=self.settings),
            refresh_token=create_refresh_token(user.id, settings=self.settings),
        )

    def create_auth_response(self, user: User) -> AuthTokenResponse:
        return AuthTokenResponse(
            user_id=user.id,
            access_token=create_access_token(user.id, settings=self.settings),
            refresh_token=create_refresh_token(user.id, settings=self.settings),
            onboarding_status=OnboardingStatus(user.onboarding_status),
        )
