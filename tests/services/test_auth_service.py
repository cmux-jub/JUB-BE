import pytest

from app.core.config import Settings
from app.core.enums import OnboardingStatus, SubscriptionTier
from app.core.exceptions import AppException
from app.core.security import decode_token, hash_password
from app.models.user import User, create_user_id
from app.schemas.auth import LoginRequest, RefreshTokenRequest, SignupRequest
from app.services.auth_service import AuthService


class FakeUserRepository:
    def __init__(self):
        self.users_by_id = {}
        self.users_by_email = {}

    async def find_by_id(self, user_id: str):
        return self.users_by_id.get(user_id)

    async def find_by_email(self, email: str):
        return self.users_by_email.get(email)

    async def create(self, user: User):
        if user.id is None:
            user.id = create_user_id()
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user
        return user


def create_test_user() -> User:
    return User(
        id="u_test",
        email="user@example.com",
        hashed_password=hash_password("password123"),
        nickname="tester",
        birth_year=1998,
        onboarding_status=OnboardingStatus.NEEDS_BANK_LINK.value,
        subscription_tier=SubscriptionTier.FREE_FULL.value,
        chatbot_usage_count=0,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret_key="test-secret")


@pytest.mark.asyncio
async def test_signup_creates_user_and_tokens(settings: Settings):
    repo = FakeUserRepository()
    service = AuthService(repo, settings=settings)

    result = await service.signup(
        SignupRequest(
            email="user@example.com",
            password="password123",
            nickname="tester",
        )
    )

    assert result.user_id.startswith("u_")
    assert result.onboarding_status == OnboardingStatus.NEEDS_BANK_LINK
    assert decode_token(result.access_token, expected_type="access", settings=settings) == result.user_id
    assert repo.users_by_email["user@example.com"].hashed_password != "password123"
    assert repo.users_by_email["user@example.com"].birth_year is None


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_email(settings: Settings):
    repo = FakeUserRepository()
    service = AuthService(repo, settings=settings)
    request = SignupRequest(
        email="user@example.com",
        password="password123",
        nickname="tester",
    )
    await service.signup(request)

    with pytest.raises(AppException) as exc_info:
        await service.signup(request)

    assert exc_info.value.code == "INVALID_INPUT"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_login_success(settings: Settings):
    repo = FakeUserRepository()
    user = create_test_user()
    repo.users_by_id[user.id] = user
    repo.users_by_email[user.email] = user
    service = AuthService(repo, settings=settings)

    result = await service.login(LoginRequest(email="user@example.com", password="password123"))

    assert result.user_id == "u_test"
    assert decode_token(result.refresh_token, expected_type="refresh", settings=settings) == "u_test"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(settings: Settings):
    repo = FakeUserRepository()
    user = create_test_user()
    repo.users_by_id[user.id] = user
    repo.users_by_email[user.email] = user
    service = AuthService(repo, settings=settings)

    with pytest.raises(AppException) as exc_info:
        await service.login(LoginRequest(email="user@example.com", password="wrong-password"))

    assert exc_info.value.code == "UNAUTHORIZED"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(settings: Settings):
    repo = FakeUserRepository()
    user = create_test_user()
    repo.users_by_id[user.id] = user
    repo.users_by_email[user.email] = user
    service = AuthService(repo, settings=settings)
    auth = service.create_auth_response(user)

    result = await service.refresh(RefreshTokenRequest(refresh_token=auth.refresh_token))

    assert decode_token(result.access_token, expected_type="access", settings=settings) == "u_test"
    assert decode_token(result.refresh_token, expected_type="refresh", settings=settings) == "u_test"
