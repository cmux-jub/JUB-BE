from typing import Annotated

from fastapi import Depends, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException, ErrorCode
from app.core.security import decode_token
from app.models.user import User
from app.repositories.chatbot_repo import ChatbotRepository
from app.repositories.retrospective_repo import RetrospectiveRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService
from app.services.banking_service import BankingService
from app.services.chatbot_service import ChatbotService
from app.services.insight_service import InsightService
from app.services.onboarding_service import OnboardingService
from app.services.retrospective_service import RetrospectiveService
from app.services.subscription_service import SubscriptionService
from app.services.transaction_service import TransactionService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_auth_service(repo: Annotated[UserRepository, Depends(get_user_repository)]) -> AuthService:
    return AuthService(repo)


def get_transaction_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> TransactionRepository:
    return TransactionRepository(db)


def get_chatbot_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> ChatbotRepository:
    return ChatbotRepository(db)


def get_retrospective_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> RetrospectiveRepository:
    return RetrospectiveRepository(db)


def get_subscription_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> SubscriptionRepository:
    return SubscriptionRepository(db)


def get_transaction_service(
    repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> TransactionService:
    return TransactionService(repo, user_repo=user_repo)


def get_banking_service(
    repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> BankingService:
    return BankingService(repo, user_repo=user_repo)


def get_onboarding_service(
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> OnboardingService:
    return OnboardingService(transaction_repo=transaction_repo, user_repo=user_repo)


def get_chatbot_service(
    chatbot_repo: Annotated[ChatbotRepository, Depends(get_chatbot_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
) -> ChatbotService:
    return ChatbotService(chatbot_repo=chatbot_repo, user_repo=user_repo, transaction_repo=transaction_repo)


def get_retrospective_service(
    retrospective_repo: Annotated[RetrospectiveRepository, Depends(get_retrospective_repository)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
    chatbot_repo: Annotated[ChatbotRepository, Depends(get_chatbot_repository)],
) -> RetrospectiveService:
    return RetrospectiveService(
        retrospective_repo=retrospective_repo,
        transaction_repo=transaction_repo,
        chatbot_repo=chatbot_repo,
    )


def get_insight_service(
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
    chatbot_repo: Annotated[ChatbotRepository, Depends(get_chatbot_repository)],
    retrospective_repo: Annotated[RetrospectiveRepository, Depends(get_retrospective_repository)],
) -> InsightService:
    return InsightService(
        transaction_repo=transaction_repo,
        chatbot_repo=chatbot_repo,
        retrospective_repo=retrospective_repo,
    )


def get_subscription_service(
    subscription_repo: Annotated[SubscriptionRepository, Depends(get_subscription_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> SubscriptionService:
    return SubscriptionService(subscription_repo=subscription_repo, user_repo=user_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise AppException(ErrorCode.UNAUTHORIZED, 401, "인증 토큰이 필요합니다")

    user_id = decode_token(credentials.credentials, expected_type="access")

    async for db in get_db():
        repo = UserRepository(db)
        user = await repo.find_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHORIZED, 401, "인증 정보를 확인할 수 없습니다")

        return user

    raise AppException(ErrorCode.UNAUTHORIZED, 401, "인증 정보를 확인할 수 없습니다")


async def get_current_websocket_user(websocket: WebSocket) -> User:
    token = websocket.query_params.get("token")
    if token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    try:
        user_id = decode_token(token, expected_type="access")
    except AppException as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc

    async for db in get_db():
        repo = UserRepository(db)
        user = await repo.find_by_id(user_id)
        if user is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

        return user

    raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
