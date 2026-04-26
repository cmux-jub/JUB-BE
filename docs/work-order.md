# Work Order

> MVP 개발 단계별 작업 순서

---

## Phase 0: 프로젝트 초기 설정

- [x] Python 프로젝트 초기화 (`pyproject.toml`, 의존성)
- [x] FastAPI 앱 엔트리포인트 (`src/app/main.py`)
- [x] PostgreSQL 연결 설정 (`core/database.py`)
- [x] Alembic 마이그레이션 초기화
- [x] Ruff 린트/포맷 설정
- [x] pre-commit hook 설정
- [x] pytest 설정 및 conftest
- [x] `.env.example` 작성
- [x] 공통 응답 스키마 (`ApiResponse`, `AppException`)
- [x] 헬스체크 엔드포인트 (`GET /health`)

---

## Phase 1: 인증 & 사용자

> API 명세 §1 대응

- [x] User 모델 (`models/user.py`)
- [x] `POST /auth/signup` — 회원가입
- [x] `POST /auth/login` — 로그인
- [x] `POST /auth/refresh` — 토큰 갱신
- [x] `GET /users/me` — 내 정보 조회
- [x] JWT 발급/검증 (`core/security.py`)
- [x] 비밀번호 해싱 (bcrypt)
- [x] 인증 의존성 (`Depends(get_current_user)`)
- [x] 테스트: 회원가입, 로그인, 토큰 갱신, 인증 실패

---

## Phase 2: 거래 & 오픈뱅킹

> API 명세 §2, §3 대응

- [x] Transaction 모델
- [x] `POST /banking/oauth/start` — OAuth 시작
- [x] `POST /banking/oauth/callback` — OAuth 콜백
- [x] `POST /banking/sync` — 거래 동기화
- [x] `GET /transactions` — 거래 목록 (커서 페이지네이션)
- [x] `GET /transactions/{id}` — 거래 상세
- [x] `PATCH /transactions/{id}/category` — 카테고리 수정
- [x] `POST /transactions/{id}/satisfaction` — 만족도 입력
- [x] 룰베이스 카테고리 분류기 (IMMEDIATE/LASTING/ESSENTIAL)
- [x] AI 카테고리 분류 (신뢰도 < 0.7일 때 OpenAI 호출)
- [x] 테스트: 거래 CRUD, 페이지네이션, 카테고리 분류

---

## Phase 3: 온보딩

> API 명세 §4 대응

- [x] `GET /onboarding/transactions-to-label` — 라벨링 대상 큐레이션
- [x] `GET /onboarding/progress` — 온보딩 진행률
- [x] `POST /onboarding/first-insight` — 첫 인사이트 카드
- [x] 온보딩 상태 관리 (NEEDS_BANK_LINK → NEEDS_LABELING → READY)
- [x] 테스트: 온보딩 플로우 전체

---

## Phase 4: 챗봇 (핵심 기능)

> API 명세 §5 대응

- [x] ChatbotSession, ChatbotMessage 모델
- [x] `POST /chatbot/sessions` — 세션 시작
- [x] WebSocket `/ws/chatbot/{session_id}` — 실시간 대화
- [x] OpenAI API 연동 (스트리밍 응답)
- [x] 시스템 프롬프트 구성 (사용자 컨텍스트 주입)
- [x] `POST /chatbot/sessions/{id}/decide` — 결정 확정 (REST 폴백)
- [x] `GET /chatbot/sessions` — 세션 목록
- [x] `GET /chatbot/sessions/{id}` — 세션 상세
- [x] 대화 요약 비동기 생성 (Celery 태스크)
- [x] 모델 티어 분기 (FULL: gpt-4o / LITE: gpt-4o-mini)
- [x] 테스트: 세션 생성, WebSocket 통신, 요약 생성

---

## Phase 5: 주간 회고

> API 명세 §6 대응

- [x] Retrospective 모델
- [x] `GET /retrospectives/current-week` — 이번 주 회고 큐레이션
- [x] `POST /retrospectives` — 회고 일괄 제출
- [x] `GET /retrospectives` — 과거 회고 이력
- [x] AI 큐레이션 (Active Learning 선정 로직)
- [x] 챗봇 세션 ↔ 회고 항목 연결
- [x] 테스트: 큐레이션, 제출, 인사이트 생성

---

## Phase 6: 인사이트 & 구독

> API 명세 §7, §8 대응

- [x] `GET /insights/happy-purchases` — 행복 소비 아카이브
- [x] `GET /insights/saved-amount` — 안 쓴 돈 카운터
- [x] `GET /insights/category-satisfaction` — 카테고리별 만족도
- [x] `GET /insights/score-trend` — 만족도 추세
- [x] Subscription 모델
- [x] `GET /subscription` — 구독 상태
- [x] `POST /subscription/upgrade` — 유료 전환
- [x] 챗봇 사용량 카운트 & 다운그레이드 로직
- [x] 테스트: 인사이트 조회, 구독 상태 변경

---

## Phase 7: 통합 & 마무리

- [x] 글로벌 에러 핸들링 점검 (에러코드 표 §10 대응)
- [x] API 전체 통합 테스트 (사용자 여정 §11)
- [x] Rate limiting 설정
- [x] CORS 설정
- [x] 로깅 구조화 (structlog)
- [x] Docker + docker-compose 설정
- [x] CI/CD 파이프라인
- [x] 배포 가이드 문서

---

## 작업 원칙

1. **Phase 순서대로** — 각 Phase는 이전 Phase에 의존
2. **API 명세 우선** — `api-specification.md`를 기준으로 구현
3. **테스트 동반** — 각 Phase 완료 시 해당 기능 테스트 포함
4. **마이그레이션** — 모델 변경 시 반드시 Alembic 마이그레이션 생성
5. **PR 단위** — Phase 또는 세부 기능 단위로 PR 생성
