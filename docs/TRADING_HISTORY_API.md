# BinnAIR 트레이딩 기록·내역 API (프론트 포워딩용)

> **대상:** 프론트엔드 — 이 API를 그대로 BFF/Next 등으로 포워딩하면 됨  
> **Base:** `/api/v1/history/*`  
> **버전:** 2026-07 (페이지네이션·equity·tick·요약 보강)  
> **관련:** [API_REFERENCE.md](./API_REFERENCE.md), [PERSISTENCE.md](./PERSISTENCE.md), [UI_CONTROL_GUIDE.md](./UI_CONTROL_GUIDE.md)

---

## 1. 한 줄 요약

| 화면 | 권장 엔드포인트 |
|------|-----------------|
| 내역 대시보드 카드 | `GET /history/summary` |
| 주문 내역 테이블 | `GET /history/orders` |
| 체결 내역 | `GET /history/executions` |
| 포지션 내역 | `GET /history/positions` |
| 청산(라운드트립) 내역 | `GET /history/trades` |
| 잔고/에퀴티 곡선 | `GET /history/equity` |
| 틱(판단) 상세 모달 | `GET /history/tick?correlation_id=` |
| 한 번에 최근 N건 | `GET /history?run_id=` (run_id 필수) |

기존 `/api/v1/orders`, `/performance/trades` 등은 **하위 호환**. 신규 화면은 **`/history/*`만** 쓰면 된다.

---

## 2. 이번 보강 요약 (프론트 영향)

| 항목 | 내용 |
|------|------|
| **페이지네이션** | 모든 목록에 `offset` + `total_count` + `has_more` |
| **기간 필터** | `from_at` / `to_at` (ISO8601, KST 저장 기준) |
| **요약 정확도** | `summary`가 limit 스캔이 아니라 DB `COUNT`/`SUM` |
| **승/패** | `summary.wins` / `losses` / `win_rate` |
| **청산 필드 보강** | `strategy_id`, `correlation_id`, `entry_notional_usdt`, `position_snapshot_id`, `hold_seconds` |
| **청산 필터** | `exit_reason`, `is_win` |
| **잔고 곡선** | `GET /history/equity` 신규 |
| **틱 상세** | `GET /history/tick` 신규 — 시그널·추론·주문·체결·포지션·청산·감사 묶음 |
| **overview** | `GET /history` 응답에 `equity` 배열 추가 |

---

## 3. 공통 규약

### 3.1 Query (공통)

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `user_id` | string | `default` | 멀티유저 대비 (현재 단일) |
| `run_id` | string | — | 엔진 세션. **가능하면 항상 전달** |
| `symbol` | string | — | 예: `XRPUSDT` |
| `from_at` / `to_at` | string | — | ISO8601. `to_at`는 **미만(`<`)** |
| `limit` | int | 엔드포인트별 | 페이지 크기 |
| `offset` | int | `0` | 건너뛸 건수 |

`run_id`는 `GET /api/v1/control/status` 또는 `GET /api/v1/engine-runs`에서 가져온다.

### 3.2 목록 응답 래퍼 (표준)

```json
{
  "items": [ ... ],
  "count": 20,
  "total_count": 137,
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

| 필드 | 의미 |
|------|------|
| `items` | 현재 페이지 데이터 |
| `count` | `items.length` |
| `total_count` | 필터 조건 전체 건수 (페이지네이션 UI) |
| `offset` / `limit` | 요청 echo |
| `has_more` | `offset + count < total_count` |

프론트 포워딩 시 **응답을 그대로 넘기면** 된다. 래퍼를 벗겨도 되지만 `total_count`는 유지 권장.

### 3.3 다음 페이지

```
offset_next = offset + limit
// has_more === true 일 때만 호출
GET ...&limit=20&offset=20
```

---

## 4. 엔드포인트 상세

### 4.1 `GET /api/v1/history/summary`

집계 카드용. **페이지가 아니라 객체 1개**.

```
GET /api/v1/history/summary?run_id=prod_timesfm_run&symbol=XRPUSDT
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `engine_status` | string\|null | `engine_run.status` (run_id 있을 때) |
| `open_positions` | int | 심볼별 최신 OPEN |
| `orders_total` / `orders_filled` / `orders_pending` | int | DB 기준 COUNT |
| `orders_missing_db_execution` | int | 거래소에만 체결 있는 샘플(실거래) |
| `executions_total` | int | 체결 건수 |
| `closed_positions` / `closed_trades` | int | CLOSED 스냅샷 / trade_result |
| `realized_pnl_sum` | float | 기간 내 실현손익 합 |
| `wins` / `losses` | int | `is_win` 기준 |
| `win_rate` | float\|null | `wins / (wins+losses)`, 없으면 null |
| `latest_signal_at` 등 | datetime\|null | 최근 활동 시각 |

---

### 4.2 `GET /api/v1/history/orders`

**주문 내역** 테이블.

추가 Query: `side`, `fill_status` (`PENDING` \| `FILLED` \| `PARTIAL` \| `REJECTED` \| `CANCELLED`)

주요 필드:

| 필드 | 설명 |
|------|------|
| `side` / `order_type` / `quantity` | 주문 요청 |
| `fill_status` | 체결 요약 상태 |
| `filled_qty` / `avg_fill_price` / `executed_at` | 체결 있으면 값 |
| `correlation_id` | 틱 상세 드릴다운 키 |
| `notional_usdt` | 명목 추정 |
| `reduce_only` | 청산 주문 여부 |

> 시그널만 있고 주문이 없으면 여기 안 나온다 → `GET /signals` 또는 `GET /history/tick`.

---

### 4.3 `GET /api/v1/history/executions`

**체결(fill)** flat 목록.

| 필드 | 설명 |
|------|------|
| `executed_qty` / `executed_price` | 체결 수량·가격 |
| `notional_usdt` | price × qty |
| `correlation_id` | 원 주문에서 조인 |
| `synced_from_exchange` | 거래소 보정 합성 여부 |

---

### 4.4 `GET /api/v1/history/positions`

**포지션 스냅샷** 이력.

추가 Query: `status=OPEN|CLOSED`, `open_only=true` (현재 보유만)

| status | UI 의미 |
|--------|---------|
| OPEN | 진입 시점 (TP/SL, unrealized) |
| CLOSED | 청산 시점 (realized, exit_reason, duration_seconds) |

---

### 4.5 `GET /api/v1/history/trades` ⭐ 청산 기록

**라운드트립 1건 = 1 row** (`trade_result`).

추가 Query:

| 파라미터 | 설명 |
|----------|------|
| `exit_reason` | `TP` \| `SL` \| `SIGNAL` 등 |
| `is_win` | `true` / `false` |

응답 필드 (보강 포함):

| 필드 | 설명 |
|------|------|
| `trade_id` | 거래 UUID |
| `side` | `LONG` \| `SHORT` |
| `entry_price` / `exit_price` | 진입·청산가 |
| `realized_pnl` / `pnl_pct` | 손익 |
| `is_win` | 승/패 |
| `exit_reason` | 청산 사유 |
| `holding_seconds` | API 계산 보유초 (opened→closed) |
| `hold_seconds` | DB 저장 보유초 (엔진 기록) |
| `entry_notional_usdt` | 진입 명목 |
| `strategy_id` | 전략 |
| `correlation_id` | 틱 상세 연결 |
| `position_snapshot_id` | CLOSED 스냅샷 FK |
| `opened_at` / `closed_at` | 시각 |
| `paper_mode` | 페이퍼 여부 |

---

### 4.6 `GET /api/v1/history/equity` ⭐ 신규

잔고 곡선 차트용. **시간 오름차순**.

```
GET /api/v1/history/equity?run_id=prod_timesfm_run&limit=200
```

| 필드 | 설명 |
|------|------|
| `snapshot_at` | 스냅샷 시각 |
| `snapshot_date` | `YYYY-MM-DD` |
| `equity_usdt` | 잔고 |
| `cumulative_realized_pnl` | 누적 실현손익 |
| `source` | 기록 출처 (엔진 start 등) |
| `paper_mode` | 페이퍼 여부 |

차트: `x = snapshot_at`, `y = equity_usdt` (또는 `cumulative_realized_pnl`).

---

### 4.7 `GET /api/v1/history/tick` ⭐ 신규

주문/시그널의 `correlation_id`로 **한 틱의 판단·실행 묶음**.

```
GET /api/v1/history/tick?correlation_id=<uuid-or-id>
```

| 필드 | 설명 |
|------|------|
| `correlation_id` | 요청 키 |
| `run_id` / `symbol` | 묶음에서 추론 |
| `signals` | 동일 correlation 시그널 |
| `inferences` | correlation 컬럼 없음 → **동일 run+symbol 최근 5건** (참고용) |
| `orders` / `executions` | 주문·체결 |
| `positions` | 동일 run+symbol 최근 10 스냅샷 |
| `trades` | 동일 correlation 청산 |
| `audit_logs` | 감사/리스크 로그 |

UI: 주문 행 클릭 → `correlation_id`로 모달 오픈.

---

### 4.8 `GET /api/v1/history` (overview)

`run_id` **필수**. summary + 최근 N건.

```
GET /api/v1/history?run_id=prod_timesfm_run&recent_limit=20
```

```json
{
  "summary": { ... },
  "orders": [ ... ],
  "executions": [ ... ],
  "positions": [ ... ],
  "trades": [ ... ],
  "equity": [ ... ]
}
```

목록 필드는 페이지 래퍼 없이 **배열만**. 대시보드 초기 로드용.

---

## 5. 프론트 포워딩 예시

Next.js Route Handler / BFF 패턴:

```ts
// GET /front-api/history/trades?run_id=...&limit=20&offset=0
const qs = new URLSearchParams(req.nextUrl.searchParams);
const res = await fetch(
  `${PROCESS_ENV.BINNAIR_API}/api/v1/history/trades?${qs}`,
  { cache: "no-store" }
);
return Response.json(await res.json(), { status: res.status });
```

권장 매핑:

| Front path | Upstream |
|------------|----------|
| `/api/history/summary` | `/api/v1/history/summary` |
| `/api/history/orders` | `/api/v1/history/orders` |
| `/api/history/executions` | `/api/v1/history/executions` |
| `/api/history/positions` | `/api/v1/history/positions` |
| `/api/history/trades` | `/api/v1/history/trades` |
| `/api/history/equity` | `/api/v1/history/equity` |
| `/api/history/tick` | `/api/v1/history/tick` |
| `/api/history` | `/api/v1/history` |

Query string **그대로 전달**하면 된다 (`user_id`, `run_id`, `offset`, `limit` 포함).

---

## 6. 화면별 호출 순서 (권장)

```text
1) GET /control/status  → run_id, trading_enabled
2) GET /history/summary?run_id=...
3) 탭별:
   - 주문:     /history/orders?run_id=&limit=20&offset=
   - 체결:     /history/executions?...
   - 포지션:   /history/positions?status=CLOSED&...
   - 청산:     /history/trades?is_win=&exit_reason=&...
   - 잔고차트: /history/equity?run_id=&limit=200
4) 행 클릭:    /history/tick?correlation_id=
```

---

## 7. 데이터 관계 (짧은 참고)

```text
inference → signal → order_request → order_execution
                  ↘ position OPEN → (TP/SL/SIGNAL) → position CLOSED → trade_result
engine start → equity_snapshot
```

- **주문 내역** ≠ 시그널 내역  
- **청산 내역(`trades`)** = 승률·PnL의 정본  
- **equity** = 잔고 곡선 / 수익률 분모에 사용

---

## 8. curl 스모크

```bash
BASE=http://127.0.0.1:8000
RUN=testnet_timesfm_run

curl "$BASE/api/v1/history/summary?run_id=$RUN"
curl "$BASE/api/v1/history/trades?run_id=$RUN&limit=20&offset=0"
curl "$BASE/api/v1/history/trades?run_id=$RUN&is_win=true"
curl "$BASE/api/v1/history/equity?run_id=$RUN&limit=100"
curl "$BASE/api/v1/history/orders?run_id=$RUN&limit=20&offset=0"
# correlation_id 는 orders/trades 응답에서 복사
curl "$BASE/api/v1/history/tick?correlation_id=YOUR_CORR_ID"
curl "$BASE/api/v1/history?run_id=$RUN&recent_limit=10"
```

---

## 9. Breaking / 주의

1. 목록 응답에 `total_count`, `offset`, `limit`, `has_more`가 **추가**됨. 기존 `items`+`count`는 유지.
2. `GET /history` overview에 `equity` 키 **추가** (기존 키 유지 않음).
3. `fill_status`로 주문 필터 시, 거래소 보정 후 페이지 `items`가 DB `total_count`보다 짧을 수 있음 (실거래 reconcile).
4. `tick.inferences`는 correlation 정확 매칭이 아님 (run+symbol 최근). UI에 “참고 추론”으로 표시 권장.
