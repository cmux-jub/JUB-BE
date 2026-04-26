from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.core.middleware import OperationalMiddleware
from app.schemas.common import ApiResponse, ErrorDetail

HTTP_ERROR_CODE_MAP = {
    400: ErrorCode.INVALID_INPUT,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    429: ErrorCode.RATE_LIMIT_EXCEEDED,
}

logger = get_logger(__name__)


def error_response(status_code: int, code: ErrorCode | str, message: str) -> JSONResponse:
    response = ApiResponse[None](
        success=False,
        data=None,
        error=ErrorDetail(code=str(code), message=message),
    )
    return JSONResponse(status_code=status_code, content=response.model_dump())


def create_app(settings: Settings | None = None) -> FastAPI:
    current_settings = settings or get_settings()
    configure_logging(current_settings)
    app = FastAPI(title=current_settings.app_name, debug=current_settings.debug)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.cors_origins,
        allow_credentials=current_settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(OperationalMiddleware, settings=current_settings)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(400, ErrorCode.INVALID_INPUT, "요청 형식이 올바르지 않습니다")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_ERROR_CODE_MAP.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        message = str(exc.detail) if exc.detail else "요청을 처리할 수 없습니다"
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_error", path=request.url.path)
        return error_response(500, ErrorCode.INTERNAL_ERROR, "서버 내부 오류가 발생했습니다")

    app.include_router(health_router)
    app.include_router(api_router, prefix=current_settings.api_v1_prefix)

    return app


app = create_app()
