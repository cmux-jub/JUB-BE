# Deployment Guide

> Aftertaste Backend 배포/운영 가이드

## 1. 런타임 요구사항

- Python 3.12+
- PostgreSQL 16
- Redis 7+
- OpenAI API Key (운영 챗봇/요약/분류 사용 시)

## 2. 필수 환경변수

| 이름 | 설명 |
|------|------|
| `APP_ENV` | `local`, `staging`, `production` 등 실행 환경 |
| `DATABASE_URL` | SQLAlchemy asyncpg 연결 문자열 |
| `REDIS_URL` | Celery/Redis broker 연결 문자열 |
| `JWT_SECRET_KEY` | JWT 서명 키. 운영에서는 강한 랜덤 값 사용 |
| `OPENAI_API_KEY` | OpenAI API Key. 비어 있으면 fallback 응답 사용 |
| `CORS_ORIGINS` | 허용할 프론트엔드 origin JSON 배열 |
| `RATE_LIMIT_ENABLED` | rate limit 활성화 여부 |
| `RATE_LIMIT_REQUESTS` | 윈도우 내 허용 요청 수 |
| `RATE_LIMIT_WINDOW_SECONDS` | rate limit 윈도우 초 |

## 3. 로컬 Docker 실행

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- Health check: `GET http://localhost:8000/health`
- Versioned health check: `GET http://localhost:8000/v1/health`

`docker-compose.yml`은 PostgreSQL, Redis, API 컨테이너를 함께 띄우며 API 시작 전에 `alembic upgrade head`를 실행합니다.

## 4. 수동 배포 순서

```bash
python -m pip install -e .
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

운영에서는 `uvicorn` 단독 실행 대신 프로세스 매니저 또는 컨테이너 오케스트레이터를 사용합니다.

## 5. CI/CD

GitHub Actions 워크플로우는 `.github/workflows/ci.yml`에 정의되어 있습니다.

1. Python 3.12 설치
2. `.[dev]` 의존성 설치
3. `ruff check .`
4. `ruff format --check .`
5. `pytest -q`

## 6. 운영 체크리스트

- `JWT_SECRET_KEY`를 기본값에서 교체
- `CORS_ORIGINS`를 실제 프론트엔드 도메인으로 제한
- `DATABASE_URL`, `REDIS_URL`을 운영 인프라로 설정
- `OPENAI_API_KEY` 등록
- 로그 수집기에서 JSON 로그 파싱 설정
- `/health` 기준 로드밸런서 health check 설정
