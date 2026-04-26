> PRD v3.1 기반 / REST + WebSocket / 작성일: 2026.04
> 

---

## 0. 공통 사항

### Base URL

- REST: `https://{baseurl}/v1`
- WebSocket: `wss://{baseurl}/v1/ws`

### 인증

- 모든 인증 필요 엔드포인트는 헤더에 `Authorization: Bearer {access_token}`
- 토큰 미발급/만료 시 `401 Unauthorized`

### 공통 응답 형식

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "사용자에게 보여줄 메시지"
  }
}
```

### 카테고리 enum

- `IMMEDIATE` (즉시 소비형: 배달/카페/술)
- `LASTING` (지속 소비형: 옷/가전/구독/강의)
- `ESSENTIAL` (필수 소비형: 교통/통신/공과금)

### 결정 enum

- `BUY` (살게요)
- `RECONSIDER` (다시 생각)
- `SKIP` (안 살게요)

---

## 1. 인증 & 사용자

### 1.1 회원가입

**`POST /auth/signup`**

요청:

```json
{
  "email": "user@example.com",
  "password": "string",
  "nickname": "string"
}
```

응답 `201`:

```json
{
  "success": true,
  "data": {
    "user_id": "u_abc123",
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "onboarding_status": "NEEDS_BANK_LINK"
  }
}
```

`onboarding_status` enum:

- `NEEDS_BANK_LINK` (오픈뱅킹 연동 필요)
- `NEEDS_LABELING` (3개월 라벨링 필요)
- `READY` (챗봇 활성화)

---

### 1.2 로그인

**`POST /auth/login`**

요청:

```json
{
  "email": "user@example.com",
  "password": "string"
}
```

응답 `200`: 1.1과 동일

---

### 1.3 토큰 갱신

**`POST /auth/refresh`**

요청:

```json
{ "refresh_token": "jwt..." }
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "access_token": "jwt...",
    "refresh_token": "jwt..."
  }
}
```

---

### 1.4 내 정보 조회

**`GET /users/me`** 🔐

응답 `200`:

```json
{
  "success": true,
  "data": {
    "user_id": "u_abc123",
    "email": "user@example.com",
    "nickname": "string",
    "onboarding_status": "READY",
    "subscription_tier": "FREE_FULL",
    "chatbot_usage_count": 3,
    "created_at": "2026-04-26T10:00:00Z"
  }
}
```

`subscription_tier` enum:

- `FREE_FULL` (첫 5회 풀기능)
- `FREE_LIMITED` (다운그레이드 상태)
- `PAID` (유료)

---

## 2. 오픈뱅킹 연동

### 2.1 OAuth 시작

**`POST /banking/oauth/start`** 🔐

요청:

```json
{ "provider": "OPEN_BANKING_KR" }
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "auth_url": "https://...",
    "state_token": "string"
  }
}
```

---

### 2.2 OAuth 콜백 처리

**`POST /banking/oauth/callback`** 🔐

요청:

```json
{
  "code": "string",
  "state_token": "string"
}
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "linked_accounts": [
      {
        "account_id": "a_xxx",
        "bank_name": "신한은행",
        "masked_number": "****-1234"
      }
    ]
  }
}
```

---

### 2.3 거래 동기화

**`POST /banking/sync`** 🔐

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
  }
}
```

---

## 3. 거래 (Transactions)

### 3.1 거래 목록 조회

**`GET /transactions`** 🔐

쿼리 파라미터:

- `from_date` (YYYY-MM-DD)
- `to_date` (YYYY-MM-DD)
- `category` (IMMEDIATE | LASTING | ESSENTIAL, optional)
- `cursor` (페이지네이션)
- `limit` (default 20, max 100)

`from_date`, `to_date`를 생략하면 기본적으로 최근 3개월 거래를 조회합니다.
`spending_comparison.difference_amount`는 이번 달 사용액 - 전달 사용액이며, 양수는 전달 대비 증가, 음수는 감소를 의미합니다.

응답 `200`:

```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "transaction_id": "t_xxx",
        "amount": 35000,
        "merchant": "스타벅스 강남점",
        "category": "IMMEDIATE",
        "category_confidence": 0.92,
        "occurred_at": "2026-04-25T19:30:00Z",
        "satisfaction_score": null,
        "satisfaction_text": null,
        "labeled_at": null
      }
    ],
    "next_cursor": "c_xxx",
    "spending_comparison": {
      "current_month_amount": 420000,
      "previous_month_amount": 380000,
      "difference_amount": 40000,
      "difference_display": "+40000"
    }
  }
}
```

---

### 3.2 거래 상세 조회

**`GET /transactions/{transaction_id}`** 🔐

응답 `200`:

```json
{
  "success": true,
  "data": {
    "transaction_id": "t_xxx",
    "amount": 35000,
    "merchant": "스타벅스 강남점",
    "merchant_mcc": "5814",
    "category": "IMMEDIATE",
    "category_confidence": 0.92,
    "occurred_at": "2026-04-25T19:30:00Z",
    "satisfaction_score": 4,
    "satisfaction_text": "분위기 좋아서 만족",
    "labeled_at": "2026-04-26T20:00:00Z",
    "linked_chatbot_session_id": null
  }
}
```

---

### 3.3 거래 카테고리 수동 변경

**`PATCH /transactions/{transaction_id}/category`** 🔐

요청:

```json
{ "category": "LASTING" }
```

응답 `200`: 거래 상세 (3.2와 동일 구조)

---

### 3.4 거래 만족도 점수 입력 (회고/온보딩 공용)

**`POST /transactions/{transaction_id}/satisfaction`** 🔐

요청:

```json
{
  "score": 4,
  "text": "오랜만에 만난 친구라 행복했음"
}
```

`score`: 1-5 정수 (필수), `text`: optional

응답 `200`:

```json
{
  "success": true,
  "data": {
    "transaction_id": "t_xxx",
    "score": 4,
    "text": "...",
    "labeled_at": "2026-04-26T20:00:00Z"
  }
}
```

---

## 4. 온보딩 (3개월 회고 라벨링)

### 4.1 온보딩용 거래 큐레이션

**`GET /onboarding/transactions-to-label`** 🔐

PRD §8 Step 2: "결제 패턴 바탕 질문(지속적 구매, 큰 지출 등)"

쿼리 파라미터:

- `limit` (default 10, max 30)

응답 `200`:

```json
{
  "success": true,
  "data": {
    "labeled_count": 0,
    "required_count": 5,
    "transactions": [
      {
        "transaction_id": "t_xxx",
        "amount": 89000,
        "merchant": "유니클로",
        "category": "LASTING",
        "occurred_at": "2026-03-12T15:00:00Z",
        "selection_reason": "LARGE_AMOUNT",
        "question": "이 89,000원의 옷, 지금 봐도 만족스러우세요?"
      },
      {
        "transaction_id": "t_yyy",
        "amount": 4500,
        "merchant": "배달의민족",
        "category": "IMMEDIATE",
        "occurred_at": "2026-03-15T22:30:00Z",
        "selection_reason": "REPEATED_PURCHASE",
        "question": "이런 늦은 시간 배달, 다시 보면 만족도가 어떠세요?"
      }
    ]
  }
}
```

`selection_reason` enum:

- `LARGE_AMOUNT` (큰 지출)
- `REPEATED_PURCHASE` (지속적 구매)
- `UNUSUAL_PATTERN` (평소와 다른 소비)
- `HIGH_UNCERTAINTY` (AI가 확신 못 함)

---

### 4.2 온보딩 진행률 조회

**`GET /onboarding/progress`** 🔐

응답 `200`:

```json
{
  "success": true,
  "data": {
    "labeled_count": 3,
    "required_count": 5,
    "is_chatbot_unlocked": false,
    "next_step": "LABEL_MORE"
  }
}
```

---

### 4.3 첫 인사이트 카드 생성

**`POST /onboarding/first-insight`** 🔐

5개 라벨링 완료 후 호출. PRD §8 Step 3.

응답 `200`:

```json
{
  "success": true,
  "data": {
    "headline": "당신은 친구와의 식사에 쓸 때 만족도가 높네요",
    "supporting_data": {
      "category": "친구 식사",
      "avg_score": 4.6,
      "count": 4
    }
  }
}
```

---

## 5. 챗봇 (결제 전 상담) - 핵심 기능

### 5.1 세션 시작

**`POST /chatbot/sessions`** 🔐

요청:

```json
{
  "initial_message": "에어팟 프로 35만원 살까 고민 중",
  "amount_hint": 350000,
  "product_hint": "에어팟 프로"
}
```

`amount_hint`, `product_hint`는 optional. AI가 메시지에서 자동 추출 가능.

응답 `201`:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xxx",
    "websocket_url": "wss://api.aftertaste.app/v1/ws/chatbot/sess_xxx",
    "started_at": "2026-04-26T10:00:00Z",
    "model_tier": "FULL"
  }
}
```

`model_tier`: `FULL` (풀 모델, FREE_FULL/PAID 사용자) | `LITE` (다운그레이드 모델, FREE_LIMITED 사용자)

---

### 5.2 챗봇 WebSocket 통신

**`WS /ws/chatbot/{session_id}`** 🔐 (쿼리: `?token={access_token}`)

### 5.2.1 클라이언트 → 서버

```json
{
  "type": "user_message",
  "content": "출퇴근 때마다 쓰니까 자주 쓸 것 같아"
}
```

```json
{
  "type": "decision",
  "decision": "BUY"
}
```

### 5.2.2 서버 → 클라이언트

**메시지 스트리밍 (토큰 단위)**

```json
{ "type": "assistant_token", "content": "지난" }
{ "type": "assistant_token", "content": " 패턴을" }
{ "type": "assistant_token", "content": " 보시면..." }
```

**메시지 완료**

```json
{
  "type": "assistant_message_done",
  "message_id": "msg_xxx",
  "full_content": "지난 패턴을 보시면...",
  "data_references": [
    { "type": "category_stat", "category": "여행", "avg_score": 4.8 },
    { "type": "transaction", "transaction_id": "t_xxx" }
  ]
}
```

**상담 종료 (사용자가 결정 버튼 클릭 후)**

```json
{
  "type": "session_closed",
  "session_id": "sess_xxx",
  "decision": "BUY",
  "summary": {
    "product": "에어팟 프로",
    "amount": 350000,
    "user_reasoning": "자주 사용 예정",
    "ai_data_shown": "만족도 상위 카테고리 비교 + 가전 카테고리 과거 이력",
    "decision": "BUY"
  }
}
```

**에러**

```json
{
  "type": "error",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "잠시 후 다시 시도해주세요"
}
```

---

### 5.3 세션 종료 (REST 백업, 결정 확정)

**`POST /chatbot/sessions/{session_id}/decide`** 🔐

WebSocket 사용 권장이지만 REST 폴백용.

요청:

```json
{ "decision": "BUY" }
```

응답 `200`:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xxx",
    "decision": "BUY",
    "summary": { ... },
    "linked_transaction_id": null
  }
}
```

`linked_transaction_id`: 1주일 이내 비슷한 가맹점/금액 결제 시 자동 연결

---

### 5.4 챗봇 세션 목록

**`GET /chatbot/sessions`** 🔐

쿼리: `from_date`, `to_date`, `decision` (필터), `cursor`, `limit`

응답 `200`:

```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": "sess_xxx",
        "started_at": "2026-04-26T10:00:00Z",
        "ended_at": "2026-04-26T10:04:00Z",
        "summary": {
          "product": "에어팟 프로",
          "amount": 350000,
          "decision": "BUY"
        },
        "linked_transaction_id": "t_xxx"
      }
    ],
    "next_cursor": "c_xxx"
  }
}
```

---

### 5.5 챗봇 세션 상세

**`GET /chatbot/sessions/{session_id}`** 🔐

응답 `200`:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xxx",
    "started_at": "...",
    "ended_at": "...",
    "messages": [
    { "role": "system", "content": "...(??? ????)" },
      { "role": "user", "content": "...", "created_at": "..." },
      { "role": "assistant", "content": "...", "created_at": "..." }
    ],
    "summary": { ... },
    "decision": "BUY",
    "linked_transaction_id": "t_xxx"
  }
}
```

---

## 6. 주간 회고

### 6.1 이번 주 회고 큐레이션 조회

**`GET /retrospectives/current-week`** 🔐

일요일에 호출하면 그 주 회고 대상 리스트 반환. PRD §3.2.

응답 `200`:

```json
{
  "success": true,
  "data": {
    "week_start": "2026-04-20",
    "week_end": "2026-04-26",
    "is_completed": false,
    "transactions": [
      {
        "transaction_id": "t_xxx",
        "amount": 35000,
        "merchant": "스타벅스",
        "category": "IMMEDIATE",
        "occurred_at": "2026-04-25T19:30:00Z",
        "selection_reason": "HIGH_SATISFACTION_REINFORCE",
        "linked_chatbot_summary": null
      },
      {
        "transaction_id": "t_yyy",
        "amount": 350000,
        "merchant": "쿠팡",
        "category": "LASTING",
        "occurred_at": "2026-04-22T14:00:00Z",
        "selection_reason": "CHATBOT_FOLLOW_UP",
        "linked_chatbot_summary": {
          "session_id": "sess_xxx",
          "user_reasoning": "출퇴근 때마다 쓰니까 자주 쓸 것 같아",
          "decision": "BUY"
        }
      }
    ]
  }
}
```

`selection_reason` enum:

- `HIGH_SATISFACTION_REINFORCE` (만족 강화)
- `LARGE_AMOUNT_GAP` (공백 메우기)
- `HIGH_UNCERTAINTY` (Active Learning)
- `DIVERSITY` (카테고리 다양성)
- `CHATBOT_FOLLOW_UP` (챗봇 상담 후속)

---

### 6.2 회고 일괄 제출

**`POST /retrospectives`** 🔐

여러 거래의 점수를 한 번에 제출.

요청:

```json
{
  "week_start": "2026-04-20",
  "entries": [
    { "transaction_id": "t_xxx", "score": 4, "text": null },
    { "transaction_id": "t_yyy", "score": 3, "text": "생각보다 안 씀" }
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
    "submitted_count": 2,
    "weekly_insight": {
      "headline": "이번 주 만족도 평균 3.7점, 지난주보다 +0.3",
      "highlight": "친구 식사 카테고리에서 가장 높은 만족"
    }
  }
}
```

---

### 6.3 과거 회고 이력

**`GET /retrospectives`** 🔐

쿼리: `from_week`, `to_week`, `cursor`, `limit`

응답 `200`:

```json
{
  "success": true,
  "data": {
    "retrospectives": [
      {
        "retrospective_id": "r_xxx",
        "week_start": "2026-04-20",
        "week_end": "2026-04-26",
        "completed_at": "...",
        "avg_score": 3.7,
        "entry_count": 6
      }
    ],
    "next_cursor": "c_xxx"
  }
}
```

---

## 7. 인사이트 (메인 화면 위젯)

### 7.1 행복 소비 아카이브

**`GET /insights/happy-purchases`** 🔐

PRD §5.1 — "내가 잘 쓴 돈 카드"

쿼리: `limit` (default 20), `cursor`

응답 `200`:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "transaction_id": "t_xxx",
        "amount": 80000,
        "merchant": "OO 식당",
        "category": "IMMEDIATE",
        "occurred_at": "2026-04-15T19:00:00Z",
        "score": 5,
        "text": "오랜만에 만난 친구"
      }
    ],
    "total_count": 47,
    "total_amount": 1820000,
    "next_cursor": "c_xxx"
  }
}
```

---

### 7.2 안 쓴 돈 카운터

**`GET /insights/saved-amount`** 🔐

PRD §5.2 — 챗봇에서 SKIP 결정한 누적 금액.

쿼리: `period` (`all` | `month` | `year`)

응답 `200`:

```json
{
  "success": true,
  "data": {
    "total_saved": 1240000,
    "skip_count": 8,
    "reconsider_count": 5,
    "recent_skips": [
      {
        "session_id": "sess_xxx",
        "product": "맥북 에어",
        "amount": 1500000,
        "decided_at": "2026-04-10T15:00:00Z"
      }
    ]
  }
}
```

---

### 7.3 카테고리별 만족도

**`GET /insights/category-satisfaction`** 🔐

쿼리: `period` (`30d` | `90d` | `all`)

응답 `200`:

```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "name": "여행",
        "avg_score": 4.8,
        "count": 3,
        "total_amount": 900000
      },
      {
        "name": "친구 식사",
        "avg_score": 4.5,
        "count": 12,
        "total_amount": 480000
      }
    ]
  }
}
```

---

### 7.4 만족도 추세

**`GET /insights/score-trend`** 🔐

쿼리: `period` (`8w` | `12w` | `6m`)

응답 `200`:

```json
{
  "success": true,
  "data": {
    "data_points": [
      { "week_start": "2026-03-02", "avg_score": 3.4 },
      { "week_start": "2026-03-09", "avg_score": 3.6 },
      { "week_start": "2026-04-20", "avg_score": 3.7 }
    ]
  }
}
```

---

## 8. 결제 (Subscription)

### 8.1 구독 상태 조회

**`GET /subscription`** 🔐

응답 `200`:

```json
{
  "success": true,
  "data": {
    "tier": "FREE_FULL",
    "chatbot_usage_count": 3,
    "chatbot_full_remaining": 2,
    "downgrades_at": null,
    "next_billing_date": null
  }
}
```

---

### 8.2 유료 전환

**`POST /subscription/upgrade`** 🔐

요청:

```json
{ "plan": "MONTHLY", "payment_method_token": "..." }
```

응답 `200`: 구독 상태

---

## 9. AI 내부 LLM 호출 명세

> 이 섹션은 외부 노출 API가 아니라, 백엔드 → OpenAI API 호출 명세.
> 

### 9.1 사용 모델

- **챗봇 풀 모드**: `gpt-4o` (FULL)
- **챗봇 라이트 모드**: `gpt-4o-mini` (LITE, 다운그레이드)
- **요약/분류 백그라운드**: `gpt-4o-mini`
- **인사이트 카피 생성**: `gpt-4o-mini`

---

### 9.2 챗봇 상담 호출

**엔드포인트 (OpenAI)**: `POST https://api.openai.com/v1/chat/completions`

**시스템 프롬프트 (구조)**:

```
당신은 Aftertaste의 담담한 상담사입니다.
- 공감형 친구처럼 호들갑 떨지 않습니다.
- "지금 기분이 어떠세요?" 같은 심리상담 질문은 하지 않습니다.
- 데이터 기반으로 사용자의 패턴을 보여줍니다.
- 결정은 사용자가 합니다. 강요하지 않습니다.

[사용자 컨텍스트]
- 이번 달 평균 만족도: {avg_score}
- 카테고리별 만족도 상위 3개: {top_categories}
- 비슷한 금액대 과거 결정: {similar_amount_history}
- 같은 카테고리 과거 만족도: {category_history}

[현재 상담]
- 입력 상품: {product_hint}
- 입력 금액: {amount_hint}
- 추정 카테고리: {category}, 신뢰도 {confidence}
```

**요청 예시**:

```json
{
  "model": "gpt-4o",
  "max_tokens": 500,
  "stream": true,
  "messages": [
    { "role": "system", "content": "...(??? ????)" },
    { "role": "user", "content": "에어팟 프로 35만원 살까 고민 중" },
    { "role": "assistant", "content": "35만원이군요. 지난 한 달간..." },
    { "role": "user", "content": "출퇴근 때마다 쓰니까 자주 쓸 것 같아" }
  ]
}
```

**스트리밍 응답 처리**:

- `chat.completion.chunk` 이벤트의 `text` → 클라이언트 WebSocket에 `assistant_token`으로 전달
- `[DONE]` → `assistant_message_done` 전송 후 DB 저장

---

### 9.3 대화 요약 생성 (세션 종료 시)

**호출 시점**: 사용자가 결정 버튼 클릭 → 세션 종료 → 비동기 작업 큐로

**시스템 프롬프트**:

```
다음 챗봇 상담 대화를 4개 필드로 요약해주세요.
JSON만 출력하고, 설명/마크다운 금지.

필드:
- product: 상담한 상품/소비 항목
- amount: 금액 (숫자, 모르면 null)
- user_reasoning: 사용자가 사려는 이유 (한 줄)
- ai_data_shown: AI가 제시한 핵심 데이터 (한 줄)
- decision: BUY | RECONSIDER | SKIP
```

**요청**:

```json
{
  "model": "gpt-4o-mini",
  "max_tokens": 300,
  "messages": [
    { "role": "system", "content": "...(??? ????)" },
    { "role": "user", "content": "[전체 대화 + 결정]" }
  ]
}
```

**응답 파싱**: JSON.parse(response.content[0].text) → DB 저장

---

### 9.4 거래 카테고리 분류

**호출 시점**: 오픈뱅킹 동기화 후 룰베이스 분류 신뢰도 < 0.7인 경우만

**시스템 프롬프트**:

```
거래 정보를 보고 IMMEDIATE/LASTING/ESSENTIAL 중 하나로 분류하세요.
- IMMEDIATE: 즉시 소비형 (배달/카페/술/충동쇼핑)
- LASTING: 지속 소비형 (옷/가전/구독/강의)
- ESSENTIAL: 필수 소비형 (교통/통신/공과금)

JSON만 출력. {"category": "...", "confidence": 0.0~1.0}
```

**모델**: `gpt-4o-mini`

---

### 9.5 회고 큐레이션 (Active Learning)

**호출 시점**: 일요일 오전, 회고 대상 선정 시.

**프롬프트**:

```
지난 주 거래 N개 중에서, 회고에 올릴 거래를 선정하세요.
선정 기준 4가지를 골고루 믹스:
1. 만족 강화 (이미 만족도 높았던 항목)
2. 공백 메우기 (큰 금액인데 라벨 없음)
3. AI 불확실 (분류 신뢰도 낮음)
4. 다양성 (카테고리 골고루)

추가 우선: 이번 주 챗봇 BUY 결정한 거래 → 무조건 포함

JSON 출력:
{ "selected": [{ "transaction_id": "...", "reason": "..." }] }
```

**모델**: `gpt-4o-mini`

---

### 9.6 인사이트 카피 생성

**호출 시점**: 첫 인사이트 카드, 주간 인사이트 헤드라인 생성 시.

**시스템 프롬프트**:

```
사용자의 소비 통계를 보고, "Aftertaste 톤"의 카피를 생성하세요.
- 따뜻하고 고요
- 죄책감 X, 강요 X
- 데이터 기반, 한 줄

예시 좋음: "당신은 친구와의 식사에 쓸 때 만족도가 높네요"
예시 나쁨: "또 충동구매 하셨네요"
```

**모델**: `gpt-4o-mini`

---

## 10. 에러 코드 표

| 코드 | HTTP | 의미 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 형식 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 한도 초과 |
| `BANK_LINK_REQUIRED` | 409 | 오픈뱅킹 미연동 |
| `LABELING_REQUIRED` | 409 | 5라벨 미달 (챗봇 활성화 안 됨) |
| `CHATBOT_QUOTA_EXCEEDED` | 402 | 무료 사용량 초과 |
| `LLM_UNAVAILABLE` | 503 | OpenAI API 일시 장애 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |

---

## 11. 호출 흐름 예시 (전체 사용자 여정)

### 11.1 신규 사용자 첫 상담까지

```
1. POST /auth/signup
2. POST /banking/oauth/start → auth_url로 리다이렉트
3. POST /banking/oauth/callback
4. POST /banking/sync (3개월치)
5. GET /onboarding/transactions-to-label
6. POST /transactions/{id}/satisfaction × 5회
7. GET /onboarding/progress → is_chatbot_unlocked: true
8. POST /onboarding/first-insight
9. POST /chatbot/sessions
10. WS /ws/chatbot/{session_id}
11. (대화)
12. WS: { "type": "decision", "decision": "BUY" }
13. (서버 비동기) OpenAI로 요약 생성 → DB 저장
```

### 11.2 일요일 회고

```
1. GET /retrospectives/current-week
2. POST /retrospectives (entries 일괄 제출)
3. (응답에 weekly_insight 포함)
```

---

## 12. Open Questions (구현 시 결정 필요)

1. **WebSocket 인증 방식**: 쿼리 토큰 vs 첫 메시지 인증 vs 쿠키
2. **챗봇 세션 타임아웃**: 무응답 N분 시 자동 종료 정책
3. **요약 실패 시 폴백**: LLM 실패 시 빈 요약 or 재시도 정책
4. **카테고리 분류 신뢰도 임계값**: 룰베이스 → LLM 호출 기준 (현재 0.7 가정)
5. **다운그레이드 사용자의 WebSocket 우선순위**: 응답 속도 차등 정책
6. **오프라인/캐싱**: 모바일 앱에서 회고 미리보기 등 오프라인 정책
