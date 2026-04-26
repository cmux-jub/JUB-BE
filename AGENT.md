# Aftertaste Backend

> AI 소비 행복 학습 서비스 — 결제 전 챗봇 상담 + 주 1회 회고

## 기술 스택

- **Framework**: FastAPI (Python 3.12+)
- **DB**: PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- **AI**: Anthropic Claude API (Opus/Sonnet/Haiku) + Langchain
- **Queue**: Celery + Redis
- **Lint/Format**: Ruff
- **Test**: pytest + pytest-asyncio

## 프로젝트 구조

```
src/app/
├── main.py              # 앱 진입점
├── core/                # 설정, DB, 인증, 의존성
├── api/v1/              # 라우터 (auth, chatbot, transactions 등)
├── models/              # SQLAlchemy 모델
├── schemas/             # Pydantic 요청/응답
├── services/            # 비즈니스 로직
├── repositories/        # DB 접근 계층
└── ai/                  # LLM 호출, 프롬프트, 분류기
```

## 레이어 규칙

```
Router → Service → Repository → DB
            ↓
         AI Module → Claude API
```

- **Router**: HTTP 처리만. 비즈니스 로직 금지
- **Service**: 비즈니스 로직. DB 직접 접근 금지
- **Repository**: 순수 쿼리만

## 코드 컨벤션 요약

- 코드(변수/함수/클래스): **영어**, 커밋/주석: **한국어**
- 네이밍: 파일·변수·함수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE`
- 타입 힌트 필수, `X | None` 사용 (`Optional` 아님)
- 응답은 항상 `ApiResponse[T]` 래퍼 사용
- 커밋: `<타입>: <한국어 요약>` (feat/fix/refactor/docs/test/chore)

## 개발 순서 (Phase)

0. 프로젝트 초기 설정 (앱 구조, DB, 린트, 테스트)
1. 인증 & 사용자 (signup, login, JWT)
2. 거래 & 오픈뱅킹 (거래 CRUD, 카테고리 분류)
3. 온보딩 (라벨링, 진행률, 첫 인사이트)
4. **챗봇** (WebSocket, Claude 스트리밍, 대화 요약) ← 핵심
5. 주간 회고 (큐레이션, 일괄 제출)
6. 인사이트 & 구독 (위젯, 결제)
7. 통합 & 마무리 (에러처리, Docker, CI/CD)

## Hook

- pre-commit: `ruff lint` → `ruff format` → `pytest`

## 상세 문서 (docs/)

| 문서 | 설명 |
|------|------|
| [prd.md](docs/prd.md) | 제품 요구사항 정의서 (v3) |
| [api-specification.md](docs/api-specification.md) | REST + WebSocket API 전체 명세 |
| [architecture.md](docs/architecture.md) | 아키텍처, 디렉토리 구조, 레이어 상세 |
| [code-convention.md](docs/code-convention.md) | 코드 컨벤션, 네이밍, 테스트, 커밋 규칙 |
| [work-order.md](docs/work-order.md) | Phase별 작업 체크리스트 |
