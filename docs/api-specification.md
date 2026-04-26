# Aftertaste Backend API Specification

> REST + WebSocket API 명세. 모든 REST 엔드포인트의 기본 경로는 `/v1`입니다.

---

## 0. 공통 규칙

### Base URL

- Local: `http://localhost:8000/v1`
- Production 예시: `https://api.aftertaste.app/v1`
- WebSocket: `/v1/ws/chatbot/{session_id}?token={access_token}`

### 인증

인증이 필요한 REST API는 HTTP Header에 access token을 전달합니다.

```http
Authorization: Bearer {access_token}
```

WebSocket은 쿼리 파라미터로 access token을 전달합니다.

```text
wss://api.aftertaste.app/v1/ws/chatbot/{session_id}?token={access_token}
```

### 공통 응답

성공:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

실패:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "요청 형식이 올바르지 않습니다"
  }
}
```

### 주요 Enum

`Category`

- `IMMEDIATE`: 즉시 소비. 배달, 카페, 편의점 등
- `LASTING`: 지속 소비. 강의, 책, 구독, 전자제품 등
- `ESSENTIAL`: 필수 소비. 교통, 통신, 공과금 등

`ChatbotDecision`

- `BUY`
- `RECONSIDER`
- `SKIP`

`OnboardingStatus`

- `NEEDS_BANK_LINK`
- `NEEDS_LABELING`
- `READY`

`SubscriptionTier`

- `FREE_FULL`
- `FREE_LIMITED`
- `PAID`

---

## 1. 공통 데이터 구조

### 1.1 금액 비교

소비 금액, 아낀 금액 비교에 공통으로 사용합니다.

```json
{
  "current_amount": 200000,
  "previous_amount": 350000,
  "difference_amount": -150000,
  "difference_percent": -42.9,
  "difference_display": "-150000",
  "difference_percent_display": "-42.9%"
}
```

`difference_percent`는 `previous_amount`가 0이면 `null`, 표시값은 `N/A`입니다.

### 1.2 소비 비교

주간 소비 비교처럼 “덜 쓴 금액”을 함께 보여줄 때 사용합니다.

```json
{
  "current_amount": 200000,
  "previous_amount": 350000,
  "difference_amount": -150000,
  "difference_percent": -42.9,
  "difference_display": "-150000",
  "difference_percent_display": "-42.9%",
  "saved_amount": 150000
}
```

### 1.3 가장 높은 행복 소비

```json
{
  "message": "tester님의 행복 소비는 지속 소비 지출입니다.",
  "category": "LASTING",
  "category_name": "지속 소비",
  "avg_score": 5.0,
  "total_amount": 89000,
  "count": 1
}
```

행복 소비 데이터가 없으면 `category`, `category_name`, `avg_score`는 `null`입니다.

### 1.4 행복 소비 아카이브 항목

```json
{
  "transaction_id": "t_xxx",
  "amount": 89000,
  "related_total_amount": 178000,
  "merchant": "유니클로",
  "category": "LASTING",
  "occurred_at": "2026-04-20T12:00:00Z",
  "score": 5,
  "text": "오래 입을 수 있어서 만족스러웠음"
}
```

- `occurred_at`: 지출 날짜
- `related_total_amount`: 같은 행복 소비 카테고리의 관련 총 지출 금액
- `text`: 회고/피드백 텍스트

---

## 2. 인증 / 사용자

### 2.1 회원가입

```http
POST /auth/signup
```

요청:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "nickname": "tester"
}
```

응답 `201`:

```json
{
  "success": true,
  "data": {
    "user_id": "u_xxx",
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "onboarding_status": "NEEDS_BANK_LINK"
  },
  "error": null
}
```

### 2.2 로그인

```http
POST /auth/login
```

요청:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

응답 `200`: 회원가입 응답과 동일합니다.

### 2.3 토큰 갱신

```http
POST /auth/refresh
```

요청:

```json
{
  "refresh_token": "jwt..."
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "access_token": "jwt...",
    "refresh_token": "jwt..."
  },
  "error": null
}
```

### 2.4 내 정보 조회

```http
GET /users/me
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "user_id": "u_xxx",
    "email": "user@example.com",
    "nickname": "tester",
    "onboarding_status": "READY",
    "subscription_tier": "FREE_FULL",
    "chatbot_usage_count": 3,
    "created_at": "2026-04-26T10:00:00Z"
  },
  "error": null
}
```

---

## 3. 오픈뱅킹 연동

### 3.1 OAuth 시작

```http
POST /banking/oauth/start
```

요청:

```json
{
  "provider": "OPEN_BANKING_KR"
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "auth_url": "https://...",
    "state_token": "state_xxx"
  },
  "error": null
}
```

### 3.2 OAuth 콜백

```http
POST /banking/oauth/callback
```

요청:

```json
{
  "code": "authorization-code",
  "state_token": "state_xxx"
}
```

### 3.3 거래 동기화

```http
POST /banking/sync
```

신규 가입자는 오픈뱅킹 동기화 후 최근 3개월 거래를 기반으로 온보딩을 진행합니다.

요청:

```json
{
  "from_date": "2026-01-26",
  "to_date": "2026-04-26"
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "synced_count": 247,
    "new_count": 12,
    "sync_id": "s_xxx"
  },
  "error": null
}
```

---

## 4. 메인 페이지

### 4.1 메인 요약

```http
GET /insights/main
```

반환 정보:

- 이번달 소비 금액
- 지난달 소비 금액
- 지난달 대비 소비 증감액과 `+/- %`
- 이번달 아낀 금액
- 지난달 아낀 금액
- 지난달 대비 아낀 금액 증감액과 `+/- %`
- 가장 높은 행복 소비 문장

응답 `200`:

```json
{
  "success": true,
  "data": {
    "monthly_spending": {
      "current_month_amount": 100000,
      "previous_month_amount": 200000,
      "difference_amount": -100000,
      "difference_percent": -50.0,
      "difference_display": "-100000",
      "difference_percent_display": "-50.0%"
    },
    "saved_amount_comparison": {
      "current_amount": 1500000,
      "previous_amount": 500000,
      "difference_amount": 1000000,
      "difference_percent": 200.0,
      "difference_display": "+1000000",
      "difference_percent_display": "+200.0%"
    },
    "top_happy_consumption": {
      "message": "tester님의 행복 소비는 지속 소비 지출입니다.",
      "category": "LASTING",
      "category_name": "지속 소비",
      "avg_score": 5.0,
      "total_amount": 89000,
      "count": 1
    },
    "saved_amount": 1500000,
    "saved_count": 1
  },
  "error": null
}
```

---

## 5. 거래

### 5.1 거래 목록 조회

```http
GET /transactions
```

쿼리:

- `from_date`: `YYYY-MM-DD`, optional
- `to_date`: `YYYY-MM-DD`, optional
- `category`: `IMMEDIATE | LASTING | ESSENTIAL`, optional
- `cursor`: optional
- `limit`: default `20`, max `100`

기본 동작:

- 날짜를 생략하면 최근 3개월 거래를 조회합니다.
- 응답의 `spending_comparison`은 이번달과 지난달 소비 비교입니다.

응답 `200`:

```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "transaction_id": "t_xxx",
        "amount": 6500,
        "merchant": "스타벅스",
        "category": "IMMEDIATE",
        "category_confidence": 0.92,
        "occurred_at": "2026-04-25T19:30:00Z",
        "satisfaction_score": null,
        "satisfaction_text": null,
        "labeled_at": null
      }
    ],
    "next_cursor": "t_next",
    "spending_comparison": {
      "current_month_amount": 420000,
      "previous_month_amount": 380000,
      "difference_amount": 40000,
      "difference_percent": 10.5,
      "difference_display": "+40000",
      "difference_percent_display": "+10.5%"
    }
  },
  "error": null
}
```

### 5.2 거래 상세 조회

```http
GET /transactions/{transaction_id}
```

### 5.3 거래 카테고리 수정

```http
PATCH /transactions/{transaction_id}/category
```

요청:

```json
{
  "category": "LASTING"
}
```

### 5.4 거래 만족도 직접 입력

```http
POST /transactions/{transaction_id}/satisfaction
```

요청:

```json
{
  "score": 4,
  "text": "다시 봐도 만족스러웠음"
}
```

`score`는 필수, `text`는 선택입니다.

---

## 6. 신규 가입 온보딩

신규 가입자는 로그인 후 오픈뱅킹으로 거래를 동기화한 뒤 최근 3개월 지출 데이터를 기반으로 온보딩 피드백을 작성합니다.

요구사항:

- AI가 최근 3개월 지출 내용을 분석해 질문을 생성합니다.
- 질문은 5~10개 범위입니다. 거래 데이터가 부족하면 가능한 질문만 반환될 수 있습니다.
- 각 질문은 1~5점 필수, 텍스트 선택입니다.
- 답변 제출 후 행복 소비 아카이브를 생성합니다.
- 저장된 만족도 정보는 구매 전 상담 챗봇 컨텍스트에 반영됩니다.

### 6.1 온보딩 질문 조회

```http
GET /onboarding/questions
```

쿼리:

- `limit`: default `10`, min `5`, max `10`

응답 `200`:

```json
{
  "success": true,
  "data": {
    "labeled_count": 0,
    "required_count": 5,
    "question_count": 5,
    "min_question_count": 5,
    "max_question_count": 10,
    "questions": [
      {
        "question_id": "oq_t_xxx",
        "transaction": {
          "transaction_id": "t_xxx",
          "amount": 89000,
          "merchant": "유니클로",
          "category": "LASTING",
          "occurred_at": "2026-04-20T12:00:00Z"
        },
        "selection_reason": "LARGE_AMOUNT",
        "pattern_summary": "기간 내 큰 지출에 해당하는 소비입니다.",
        "question": {
          "title": "큰 금액이었던 이 소비는 다시 봐도 만족스러웠나요?",
          "body": "유니클로에서 쓴 89,000원이 금액만큼의 만족이나 효용을 남겼는지 1~5점으로 평가해 주세요.",
          "answer_type": "SCORE_WITH_TEXT",
          "score_scale": {
            "min": 1,
            "max": 5,
            "min_label": "금액 대비 아쉬웠어요",
            "max_label": "충분히 만족했어요"
          },
          "required": true
        }
      }
    ]
  },
  "error": null
}
```

### 6.2 온보딩 답변 제출

```http
POST /onboarding/feedback
```

요청:

```json
{
  "answers": [
    {
      "question_id": "oq_t_xxx",
      "transaction_id": "t_xxx",
      "score": 5,
      "text": "오래 입을 수 있어서 만족스러웠음"
    }
  ]
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "labeled_count": 5,
    "required_count": 5,
    "is_chatbot_unlocked": true,
    "chatbot_context_ready": true,
    "first_insight": {
      "headline": "당신은 지속 소비에 쓸 때 만족도가 높네요",
      "supporting_data": {
        "category": "지속 소비",
        "avg_score": 4.6,
        "count": 3
      }
    },
    "top_happy_consumption": {
      "message": "tester님의 행복 소비는 지속 소비 지출입니다.",
      "category": "LASTING",
      "category_name": "지속 소비",
      "avg_score": 5.0,
      "total_amount": 89000,
      "count": 1
    },
    "happy_purchase_archive": [
      {
        "transaction_id": "t_xxx",
        "amount": 89000,
        "related_total_amount": 89000,
        "merchant": "유니클로",
        "category": "LASTING",
        "occurred_at": "2026-04-20T12:00:00Z",
        "score": 5,
        "text": "오래 입을 수 있어서 만족스러웠음"
      }
    ]
  },
  "error": null
}
```

호환 엔드포인트:

- `GET /onboarding/transactions-to-label`
- `GET /onboarding/progress`
- `POST /onboarding/first-insight`

---

## 7. 구매 전 챗봇 상담

### 7.1 챗봇 세션 시작

```http
POST /chatbot/sessions
```

요청:

```json
{
  "initial_message": "에어팟 프로를 살지 고민 중이야",
  "amount_hint": 350000,
  "product_hint": "에어팟 프로"
}
```

응답 `201`:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xxx",
    "websocket_url": "/v1/ws/chatbot/sess_xxx",
    "started_at": "2026-04-26T10:00:00Z",
    "model_tier": "FULL"
  },
  "error": null
}
```

챗봇은 온보딩/주간 회고에서 저장된 만족도 데이터를 기반으로 사용자 컨텍스트를 구성합니다.

### 7.2 WebSocket 상담

```text
WS /ws/chatbot/{session_id}?token={access_token}
```

클라이언트 메시지:

```json
{
  "type": "user_message",
  "content": "출퇴근길에 자주 쓸 것 같아"
}
```

서버 토큰 스트리밍:

```json
{
  "type": "assistant_token",
  "content": "최근 "
}
```

결정:

```json
{
  "type": "decision",
  "decision": "SKIP"
}
```

### 7.3 세션 결정 확정

```http
POST /chatbot/sessions/{session_id}/decide
```

요청:

```json
{
  "decision": "BUY"
}
```

### 7.4 세션 목록 / 상세

```http
GET /chatbot/sessions
GET /chatbot/sessions/{session_id}
```

---

## 8. 주간 피드백

주간 피드백은 최근 3개월 만족도 데이터와 이번 주 지출을 함께 보고 질문을 생성합니다.

요구사항:

- 일주일간 데이터를 바탕으로 질문을 생성합니다.
- 최근 3개월 데이터와 비교해 질문 컨텍스트를 보강합니다.
- 질문은 5~10개 범위입니다. 거래 데이터가 부족하면 가능한 질문만 반환될 수 있습니다.
- 각 질문은 1~5점 필수, 텍스트 선택입니다.
- 답변 제출 후 주간 인사이트(만족도 평균, 하이라이트)를 반환합니다.
- 주간 요약(소비 비교, 아낀 금액, 행복 소비 아카이브)은 별도 조회 API로 확인합니다.

### 8.1 이번 주 피드백 질문 조회

```http
GET /retrospectives/current-week
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "week_start": "2026-04-20",
    "week_end": "2026-04-26",
    "is_completed": false,
    "question_count": 5,
    "min_question_count": 5,
    "max_question_count": 10,
    "questions": [
      {
        "question_id": "rq_t_xxx",
        "transaction": {
          "transaction_id": "t_xxx",
          "amount": 35000,
          "merchant": "스타벅스",
          "category": "IMMEDIATE",
          "occurred_at": "2026-04-25T19:30:00Z"
        },
        "selection_reason": "DIVERSITY",
        "pattern_summary": "이번 기간 소비 패턴을 대표하는 항목입니다.",
        "question": {
          "title": "이번 소비는 한 주를 돌아봤을 때 만족스러웠나요?",
          "body": "스타벅스에서 쓴 35,000원이 나에게 남긴 만족도를 기록해 주세요.",
          "answer_type": "SCORE_WITH_TEXT",
          "score_scale": {
            "min": 1,
            "max": 5,
            "min_label": "아쉬웠어요",
            "max_label": "만족스러웠어요"
          },
          "required": true
        },
        "linked_chatbot_summary": null
      }
    ]
  },
  "error": null
}
```

### 8.2 주간 피드백 답변 제출

```http
POST /retrospectives
```

요청:

```json
{
  "week_start": "2026-04-20",
  "answers": [
    {
      "question_id": "rq_t_xxx",
      "transaction_id": "t_xxx",
      "score": 4,
      "text": "커피값은 컸지만 친구와 오래 이야기해서 만족스러웠어요."
    }
  ]
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "retrospective_id": "r_xxx",
    "week_start": "2026-04-20",
    "completed_at": "2026-04-26T20:00:00Z",
    "submitted_count": 5,
    "weekly_insight": {
      "headline": "이번 주 만족도 평균 4.0점, 지난주보다 +0.3",
      "highlight": "지속 소비 카테고리에서 가장 높은 만족"
    }
  },
  "error": null
}
```

### 8.3 주간 요약 조회

회고 제출 후 주간 소비 요약을 별도로 조회합니다.

```http
GET /retrospectives/{retrospective_id}/weekly-summary
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "retrospective_id": "r_xxx",
    "week_start": "2026-04-20",
    "week_end": "2026-04-26",
    "spending_comparison": {
      "current_amount": 200000,
      "previous_amount": 350000,
      "difference_amount": -150000,
      "difference_percent": -42.9,
      "difference_display": "-150000",
      "difference_percent_display": "-42.9%",
      "saved_amount": 150000
    },
    "saved_amount_comparison": {
      "current_amount": 350000,
      "previous_amount": 0,
      "difference_amount": 350000,
      "difference_percent": null,
      "difference_display": "+350000",
      "difference_percent_display": "N/A"
    },
    "top_happy_consumption": {
      "message": "tester님의 행복 소비는 지속 소비 지출입니다.",
      "category": "LASTING",
      "category_name": "지속 소비",
      "avg_score": 4.0,
      "total_amount": 200000,
      "count": 1
    },
    "happy_purchase_archive": [
      {
        "transaction_id": "t_xxx",
        "amount": 35000,
        "related_total_amount": 35000,
        "merchant": "스타벅스",
        "category": "IMMEDIATE",
        "occurred_at": "2026-04-25T19:30:00Z",
        "score": 4,
        "text": "친구와 오래 이야기해서 만족스러웠어요."
      }
    ]
  },
  "error": null
}
```

### 8.4 과거 회고 목록

```http
GET /retrospectives
```

쿼리:

- `from_week`: `YYYY-MM-DD`, optional
- `to_week`: `YYYY-MM-DD`, optional
- `cursor`: optional
- `limit`: default `20`, max `100`

---

## 9. 행복 소비 / 인사이트

### 9.1 행복 소비 아카이브 조회

```http
GET /insights/happy-purchases
```

쿼리:

- `limit`: default `20`, max `100`
- `cursor`: optional

응답 `200`:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "transaction_id": "t_xxx",
        "amount": 35000,
        "related_total_amount": 80000,
        "merchant": "스타벅스",
        "category": "IMMEDIATE",
        "occurred_at": "2026-04-25T19:30:00Z",
        "score": 5,
        "text": "친구와 오래 이야기해서 만족스러웠어요."
      }
    ],
    "total_count": 47,
    "total_amount": 1820000,
    "next_cursor": null
  },
  "error": null
}
```

### 9.2 안 쓴 돈 카운터

```http
GET /insights/saved-amount
```

쿼리:

- `period`: `all | month | year`

응답 `200`:

```json
{
  "success": true,
  "data": {
    "total_saved": 1500000,
    "skip_count": 1,
    "reconsider_count": 0,
    "recent_skips": [
      {
        "session_id": "sess_xxx",
        "product": "맥북",
        "amount": 1500000,
        "decided_at": "2026-04-10T15:00:00Z"
      }
    ]
  },
  "error": null
}
```

### 9.3 카테고리별 만족도

```http
GET /insights/category-satisfaction
```

쿼리:

- `period`: `30d | 90d | all`

### 9.4 만족도 추세

```http
GET /insights/score-trend
```

쿼리:

- `period`: `8w | 12w | 6m`

---

## 10. 구독

### 10.1 구독 상태 조회

```http
GET /subscription
```

### 10.2 유료 전환

```http
POST /subscription/upgrade
```

요청:

```json
{
  "plan": "MONTHLY",
  "payment_method_token": "payment-token"
}
```

---

## 11. AI 내부 호출

### 11.1 거래 카테고리 분류

오픈뱅킹 동기화 후 룰 기반 분류 신뢰도 `< 0.7`일 때 OpenAI 분류를 호출합니다.

### 11.2 온보딩 질문 생성

`GET /onboarding/questions`에서 최근 3개월 미라벨 거래를 후보로 전달합니다.

### 11.3 주간 피드백 질문 생성

`GET /retrospectives/current-week`에서 이번 주 거래와 최근 3개월 라벨 데이터를 함께 전달합니다.

### 11.4 챗봇 응답 생성

챗봇은 라벨링된 거래의 카테고리별 만족도 평균을 사용자 컨텍스트로 사용합니다.

---

## 12. 호출 흐름

### 12.1 신규 가입자

```text
1. POST /auth/signup
2. POST /banking/oauth/start
3. POST /banking/oauth/callback
4. POST /banking/sync
5. GET /onboarding/questions
6. POST /onboarding/feedback
7. GET /insights/main
8. POST /chatbot/sessions
```

### 12.2 기존 사용자 메인/주간 피드백

```text
1. GET /insights/main
2. GET /retrospectives/current-week
3. POST /retrospectives
4. GET /retrospectives/{retrospective_id}/weekly-summary
5. GET /insights/happy-purchases
6. GET /insights/saved-amount
```

---

## 13. 에러 코드

| code | HTTP | 의미 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 형식 오류 |
| `UNAUTHORIZED` | 401 | 인증 실패 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 제한 초과 |
| `BANK_LINK_REQUIRED` | 409 | 오픈뱅킹 연동 필요 |
| `LABELING_REQUIRED` | 409 | 라벨링 미완료 |
| `CHATBOT_QUOTA_EXCEEDED` | 402 | 챗봇 무료 사용량 초과 |
| `LLM_UNAVAILABLE` | 503 | OpenAI API 일시 장애 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |
