from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aftertaste Backend"
    app_env: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_allow_credentials: bool = True
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/aftertaste"

    jwt_secret_key: str = Field(default="change-me-to-random-secret")
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    openai_api_key: str = ""
    openai_chat_full_model: str = "gpt-4o"
    openai_chat_lite_model: str = "gpt-4o-mini"
    openai_background_model: str = "gpt-4o-mini"
    redis_url: str = "redis://localhost:6379/0"

    open_banking_client_id: str = ""
    open_banking_client_secret: str = ""
    open_banking_redirect_uri: str = "http://localhost:8000/v1/banking/oauth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
