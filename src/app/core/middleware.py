from time import perf_counter
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.core.rate_limit import InMemoryRateLimiter, get_rate_limit_key, should_skip_rate_limit
from app.schemas.common import ApiResponse, ErrorDetail


class OperationalMiddleware:
    def __init__(self, app: Any, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.rate_limiter = InMemoryRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        self.logger = get_logger(__name__)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if self.settings.rate_limit_enabled and not should_skip_rate_limit(request):
            rate_limit_key = get_rate_limit_key(request)
            if not self.rate_limiter.is_allowed(rate_limit_key):
                response = self.rate_limit_response()
                await response(scope, receive, send)
                return

        started_at = perf_counter()
        status_code = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            self.logger.info(
                "http_request",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=duration_ms,
            )

    @staticmethod
    def rate_limit_response() -> JSONResponse:
        response = ApiResponse[None](
            success=False,
            data=None,
            error=ErrorDetail(code=ErrorCode.RATE_LIMIT_EXCEEDED.value, message="잠시 후 다시 시도해주세요"),
        )
        return JSONResponse(status_code=429, content=response.model_dump())
