# Code Convention

> Python 3.12+ / FastAPI / Ruff

---

## 언어 규칙

| 대상 | 언어 |
|------|------|
| 변수, 함수, 클래스명 | 영어 |
| 커밋 메시지 | 한국어 |
| 코드 주석 | 한국어 (필요한 경우만) |
| 문서 (docs/) | 한국어 |
| API 에러 메시지 | 한국어 (사용자 노출) |

---

## 네이밍

| 대상 | 스타일 | 예시 |
|------|--------|------|
| 파일명 | snake_case | `chatbot_service.py` |
| 변수, 함수 | snake_case | `get_current_user` |
| 클래스 | PascalCase | `ChatbotSession` |
| 상수 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Pydantic 스키마 | PascalCase + 접미사 | `LoginRequest`, `LoginResponse` |
| SQLAlchemy 모델 | PascalCase (단수) | `User`, `Transaction` |
| DB 테이블명 | snake_case (복수) | `users`, `transactions` |
| Enum | PascalCase (클래스), UPPER_SNAKE (값) | `Category.IMMEDIATE` |
| API 경로 | kebab-case | `/chatbot/sessions/{session_id}/decide` |
| 환경변수 | UPPER_SNAKE | `DATABASE_URL` |

---

## 타입 힌트

모든 함수에 파라미터 타입과 리턴 타입을 명시한다.

```python
# Good
async def get_user_by_id(user_id: str) -> User | None:
    ...

# Bad
async def get_user_by_id(user_id):
    ...
```

`Optional[X]` 대신 `X | None` 사용 (Python 3.10+ 문법).

---

## Import 순서

Ruff의 isort 규칙을 따른다:

```python
# 1. 표준 라이브러리
from datetime import datetime
from typing import Annotated

# 2. 서드파티
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 로컬 모듈
from app.core.deps import get_current_user
from app.schemas.auth import LoginRequest
```

---

## 프로젝트 구조 규칙

### Router (API 레이어)

```python
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[LoginResponse]:
    result = await service.login(request.email, request.password)
    return ApiResponse(success=True, data=result)
```

- 비즈니스 로직을 Router에 작성하지 않는다
- `Depends()`로 Service 주입
- 응답은 항상 `ApiResponse[T]`로 래핑

### Service (비즈니스 레이어)

```python
class AuthService:
    def __init__(self, repo: UserRepository, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def login(self, email: str, password: str) -> LoginResponse:
        user = await self.repo.find_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401)
        ...
```

- DB 직접 접근 금지 → Repository 사용
- 트랜잭션 경계 관리

### Repository (데이터 레이어)

```python
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

- 순수 쿼리만 작성
- 비즈니스 로직 금지

---

## 에러 처리

### 커스텀 예외 사용

```python
class AppException(Exception):
    def __init__(self, code: str, status_code: int, message: str):
        self.code = code
        self.status_code = status_code
        self.message = message

# 사용
raise AppException("LABELING_REQUIRED", 409, "5개 이상 라벨링이 필요합니다")
```

### 글로벌 핸들러에서 ApiResponse 형식으로 변환

```python
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
    )
```

---

## 테스트

| 규칙 | 설명 |
|------|------|
| 파일명 | `test_` 접두사: `test_auth_service.py` |
| 함수명 | `test_` 접두사: `test_login_success` |
| 네이밍 패턴 | `test_<행위>_<조건/결과>` |
| fixture | `conftest.py`에 공통 fixture 정의 |
| DB 테스트 | 테스트용 PostgreSQL + 트랜잭션 롤백 |
| 비동기 테스트 | `@pytest.mark.asyncio` 데코레이터 사용 |

```python
@pytest.mark.asyncio
async def test_login_success(auth_service, test_user):
    result = await auth_service.login(test_user.email, "password123")
    assert result.access_token is not None
```

---

## 커밋 메시지

```
<타입>: <요약> (한국어)

[본문] (선택)
```

### 타입

| 타입 | 용도 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 리팩토링 |
| `docs` | 문서 |
| `test` | 테스트 |
| `chore` | 빌드, 설정 등 |

### 예시

```
feat: 챗봇 세션 시작 API 구현
fix: JWT 만료 시 refresh 토큰 검증 오류 수정
docs: API 명세 에러코드 표 추가
```

---

## Ruff 설정

`pyproject.toml`에서 관리:

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
# E: pycodestyle errors
# F: pyflakes
# I: isort
# N: pep8-naming
# W: pycodestyle warnings
# UP: pyupgrade
# B: bugbear
# SIM: simplify

[tool.ruff.format]
quote-style = "double"
```
