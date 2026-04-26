from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppException, ErrorCode
from app.main import create_app


def test_cors_preflight_allows_configured_origin():
    app = create_app(
        Settings(
            jwt_secret_key="test-secret",
            rate_limit_enabled=False,
            cors_origins=["http://localhost:3000"],
        )
    )
    with TestClient(app) as client:
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rate_limit_returns_common_error_shape():
    app = create_app(Settings(jwt_secret_key="test-secret", rate_limit_requests=1, rate_limit_window_seconds=60))
    with TestClient(app) as client:
        first_response = client.get("/missing")
        second_response = client.get("/missing")

    assert first_response.status_code == 404
    assert second_response.status_code == 429
    assert second_response.json() == {
        "success": False,
        "data": None,
        "error": {"code": "RATE_LIMIT_EXCEEDED", "message": "잠시 후 다시 시도해주세요"},
    }


def test_app_exception_returns_common_error_shape():
    app = create_app(Settings(jwt_secret_key="test-secret", rate_limit_enabled=False))

    @app.get("/boom")
    async def boom():
        raise AppException(ErrorCode.FORBIDDEN, 403, "권한이 없습니다")

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 403
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {"code": "FORBIDDEN", "message": "권한이 없습니다"},
    }
