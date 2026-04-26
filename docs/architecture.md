# Architecture

> Aftertaste Backend — FastAPI + PostgreSQL

---

## 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| Framework | FastAPI | 비동기, WebSocket 네이티브 지원 |
| Language | Python 3.12+ | type hint 필수 |
| DB | PostgreSQL 16 | JSON 컬럼 활용 (챗봇 대화 등) |
| ORM | SQLAlchemy 2.0 + Alembic | async session, 마이그레이션 |
| Auth | JWT (PyJWT) | access + refresh 토큰 |
| Validation | Pydantic v2 | 요청/응답 스키마 |
| AI | Anthropic Python SDK | Claude API 호출 |
| Task Queue | Celery + Redis | 요약 생성 등 비동기 작업 |
| Test | pytest + pytest-asyncio | 비동기 테스트 지원 |
| Lint | Ruff | 린트 + 포맷팅 통합 |
| WebSocket | FastAPI WebSocket | 챗봇 실시간 스트리밍 |

---

## 디렉토리 구조

```
JUP-BE/
├── docs/                    # 프로젝트 문서
├── alembic/                 # DB 마이그레이션
│   └── versions/
├── src/
│   └── app/
│       ├── main.py          # FastAPI 앱 진입점
│       ├── core/            # 공통 설정
│       │   ├── config.py    # 환경변수, 설정
│       │   ├── database.py  # DB 세션, 엔진
│       │   ├── security.py  # JWT 발급/검증
│       │   └── deps.py      # 공통 의존성 (get_db, get_current_user)
│       ├── api/
│       │   └── v1/
│       │       ├── router.py        # v1 라우터 통합
│       │       ├── auth.py          # 회원가입, 로그인, 토큰 갱신
│       │       ├── users.py         # 내 정보 조회
│       │       ├── banking.py       # 오픈뱅킹 연동
│       │       ├── transactions.py  # 거래 CRUD, 만족도 입력
│       │       ├── onboarding.py    # 온보딩 큐레이션, 진행률
│       │       ├── chatbot.py       # 챗봇 REST + WebSocket
│       │       ├── retrospectives.py# 주간 회고
│       │       ├── insights.py      # 인사이트 위젯
│       │       └── subscription.py  # 구독/결제
│       ├── models/          # SQLAlchemy 모델
│       │   ├── user.py
│       │   ├── transaction.py
│       │   ├── chatbot_session.py
│       │   ├── chatbot_message.py
│       │   ├── retrospective.py
│       │   └── subscription.py
│       ├── schemas/         # Pydantic 스키마 (요청/응답)
│       │   ├── common.py    # ApiResponse, ErrorResponse
│       │   ├── auth.py
│       │   ├── transaction.py
│       │   ├── chatbot.py
│       │   ├── retrospective.py
│       │   └── insight.py
│       ├── services/        # 비즈니스 로직
│       │   ├── auth_service.py
│       │   ├── banking_service.py
│       │   ├── transaction_service.py
│       │   ├── chatbot_service.py
│       │   ├── retrospective_service.py
│       │   ├── insight_service.py
│       │   └── subscription_service.py
│       ├── repositories/    # DB 접근 계층
│       │   ├── user_repo.py
│       │   ├── transaction_repo.py
│       │   ├── chatbot_repo.py
│       │   └── retrospective_repo.py
│       └── ai/              # AI/LLM 통합
│           ├── client.py    # Anthropic SDK 래퍼
│           ├── prompts.py   # 시스템 프롬프트 관리
│           ├── classifier.py    # 거래 카테고리 분류
│           ├── summarizer.py    # 대화 요약
│           └── curator.py       # 회고 큐레이션
├── tests/
│   ├── conftest.py          # 공통 fixture
│   ├── api/                 # API 엔드포인트 테스트
│   ├── services/            # 서비스 단위 테스트
│   └── ai/                  # AI 모듈 테스트
├── pyproject.toml           # 의존성, 린트/포맷 설정
├── alembic.ini
├── .env.example
├── .pre-commit-config.yaml
└── CLAUDE.md
```

---

## 레이어 구조

```
Request → API Router → Service → Repository → DB
                         ↓
                      AI Module → Anthropic API
```

| 레이어 | 책임 | 규칙 |
|--------|------|------|
| **API (Router)** | HTTP 요청/응답 처리, 인증 확인 | 비즈니스 로직 금지. Service 호출만 |
| **Service** | 비즈니스 로직, 트랜잭션 관리 | DB 직접 접근 금지. Repository 사용 |
| **Repository** | DB 쿼리 실행, 데이터 매핑 | 비즈니스 로직 금지. 순수 쿼리만 |
| **AI Module** | LLM 호출, 프롬프트 관리 | Service에서만 호출 |
| **Schema** | 요청/응답 직렬화, 검증 | Pydantic v2 모델 |
| **Model** | DB 테이블 매핑 | SQLAlchemy 2.0 선언적 매핑 |

---

## 공통 응답 래퍼

API 명세의 `{ success, data, error }` 형식을 Pydantic으로 통일:

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
```

---

## 인증 흐름

1. 로그인/회원가입 → access_token (30분) + refresh_token (7일) 발급
2. 인증 필요 엔드포인트 → `Depends(get_current_user)` 로 JWT 검증
3. 만료 시 `/auth/refresh` 로 갱신

---

## 챗봇 WebSocket 흐름

```
Client                    Server                     Claude API
  │── POST /chatbot/sessions ──►│                          │
  │◄── { session_id, ws_url } ──│                          │
  │                              │                          │
  │── WS connect ──────────────►│                          │
  │── user_message ────────────►│── messages.create ──────►│
  │                              │   (stream=True)          │
  │◄── assistant_token ─────────│◄── content_block_delta ──│
  │◄── assistant_token ─────────│◄── content_block_delta ──│
  │◄── assistant_message_done ──│◄── message_stop ─────────│
  │                              │                          │
  │── decision: BUY ───────────►│                          │
  │◄── session_closed ──────────│── (async) 요약 생성 ────►│
```
