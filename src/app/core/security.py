from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException, ErrorCode

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    return create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=current_settings.jwt_access_token_expire_minutes),
        settings=current_settings,
    )


def create_refresh_token(user_id: str, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    return create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=current_settings.jwt_refresh_token_expire_days),
        settings=current_settings,
    )


def create_token(user_id: str, token_type: str, expires_delta: timedelta, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()

    try:
        payload = jwt.decode(token, current_settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise AppException(ErrorCode.UNAUTHORIZED, 401, "유효하지 않은 인증 토큰입니다") from exc

    token_type = payload.get("type")
    subject = payload.get("sub")
    if token_type != expected_type or not isinstance(subject, str):
        raise AppException(ErrorCode.UNAUTHORIZED, 401, "유효하지 않은 인증 토큰입니다")

    return subject
