# BinnAIR Trading Monitor API — 프론트엔드 연동 가이드

> **read-only** API. 매매 제어(start/stop/주문) 없음. DB 이력 조회 전용.

---

## 1. 기본 정보

| 항목 | 값 |
|------|-----|
| Base URL | `http://127.0.0.1:8000` (config `api.host` / `api.port`) |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| Method | **GET only** |
| Auth | 없음 (v1) |
| Content-Type | `application/json` |
| datetime | ISO 8601 문자열 (예: `"2026-07-02T14:32:01+00:00"`) |

### 공통 Query Parameters

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `user_id` | string | `"default"` | 사용자별 이력 필터 |
| `run_id` | string | — | 실행 세션 ID (config `run_context.run_id`) |
| `symbol` | string | — | 예: `BTCUSDT` |
| `limit` | int | 엔드포인트별 | 조회 건수 상한 |

### 목록 응답 공통 형태

```json
{
  "items": [ ... ],
  "count": 0
}
```

---

## 2. 권장 화면 구성

### Page 1 — 대시보드 (메인)

**API:** `GET /api/v1/dashboard`

```
┌─────────────────────────────────────────────────────────────┐
│  BinnAIR Monitor          run: testnet_timesfm_run  ● running│
├─────────────────────────────────────────────────────────────┤
│  BTCUSDT  │  OPEN LONG  │  qty 0.002  │  entry 97200        │
│  TP 98172 │  SL 96714   │  unrealized +0.42 USDT            │
├─────────────────────────────────────────────────────────────┤
│  오늘 청산 2건  │  Realized PnL  +12.5 USDT                   │
├─────────────────────────────────────────────────────────────┤
│  최근 흐름 (recent_timeline)                                 │
│  ● 14:32  signal   Signal BUY conf=0.71                       │
│  ● 14:31  inference TimesFM HOLD                            │
│  ● 14:30  audit    Audit risk_rejected (duplicate_order)    │
└─────────────────────────────────────────────────────────────┘
```

- **5~10초 polling** 권장 (`/dashboard` 또는 `/flow/timeline`)
- OPEN 포지션 없으면 포지션 카드 숨김 / "No position" 표시

---

### Page 2 — 매매 흐름 타임라인 (상세)

**API:** `GET /api/v1/flow/timeline?run_id=...&limit=100`

필터: `run_id`, `symbol`, `user_id`

| event_type | UI 표시 | payload 상세 API |
|------------|---------|------------------|
| `inference` | 🤖 TimesFM | `payload.output_prediction.action` |
| `signal` | 📊 Signal | `payload.signal_action` BUY/SELL/HOLD |
| `order_request` | 📝 Order | `payload.request` |
| `order_execution` | ✅ Fill | `payload` (OrderExecutionDTO) |
| `position` | 📈 Position | OPEN/CLOSED, TP/SL, PnL |
| `audit` | ⚠️ Audit | `payload.event`, `payload.data.reason` |

`correlation_id`로 같은 tick 이벤트끼리 그룹핑 가능.

---

### Page 3 — 포지션

| 탭 | API |
|----|-----|
| 현재 포지션 | `GET /api/v1/positions/open` |
| 전체 이력 | `GET /api/v1/positions?status=OPEN\|CLOSED` |

CLOSED 행: `exit_reason` (TAKE_PROFIT | STOP_LOSS | MODEL_SELL), `realized_pnl`, `exit_price`

---

### Page 4 — 실행 세션

**API:** `GET /api/v1/engine-runs`, `GET /api/v1/engine-runs/{run_id}`

| status | UI |
|--------|-----|
| `running` | 🟢 |
| `stopped` | ⚪ |
| `error` | 🔴 |

---

### Page 5 — 상세 탭 (선택)

| 탭 | API |
|----|-----|
| 시그널 | `GET /api/v1/signals` |
| 모델 추론 | `GET /api/v1/inferences` |
| 주문 | `GET /api/v1/orders` |
| 감사/리스크 | `GET /api/v1/audit-logs` |

---

## 3. API 엔드포인트 명세

### `GET /health`

```json
{ "status": "ok" }
```

---

### `GET /api/v1/dashboard`

**Response: `DashboardSummaryDTO`**

```json
{
  "user_id": "default",
  "latest_run": { /* EngineRunDTO | null */ },
  "open_positions": [ /* PositionSnapshotDTO[] */ ],
  "closed_positions_today": 0,
  "realized_pnl_today": 0.0,
  "recent_timeline": [ /* FlowTimelineItemDTO[] */ ]
}
```

---

### `GET /api/v1/flow/timeline`

**Response:** `{ items: FlowTimelineItemDTO[], count: number }`

---

### `GET /api/v1/engine-runs`

Query: `user_id`, `status?`, `limit?` (default 20)

**Response:** `{ items: EngineRunDTO[], count: number }`

---

### `GET /api/v1/engine-runs/{run_id}`

**Response:** `EngineRunDTO`  
**404:** run 없음

---

### `GET /api/v1/positions/open`

**Response:** `{ items: PositionSnapshotDTO[], count: number }`

---

### `GET /api/v1/positions`

Query: `user_id`, `run_id?`, `symbol?`, `status?` (OPEN|CLOSED), `limit?` (default 50)

---

### `GET /api/v1/signals`

Query: `user_id`, `run_id?`, `symbol?`, `limit?` (default 100)

**Response:** `{ items: SignalEventDTO[], count: number }`

---

### `GET /api/v1/inferences`

**Response:** `{ items: ModelInferenceEventDTO[], count: number }`

---

### `GET /api/v1/orders`

**Response:** `{ items: OrderFlowDTO[], count: number }`

---

### `GET /api/v1/audit-logs`

**Response:** `{ items: AuditLogDTO[], count: number }`

---

## 4. DTO 스키마 (TypeScript 참고)

```typescript
// ── 테이블 DTO ──────────────────────────────────────────

interface EngineRunDTO {
  id?: number;
  user_id: string;
  run_id: string;
  strategy_id: string;
  model_version: string;
  feature_set_version: string;
  version: string;
  paper_mode: boolean;
  status: "running" | "stopped" | "error";
  started_at: string;       // ISO datetime
  stopped_at?: string | null;
  config_snapshot?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface PositionSnapshotDTO {
  id?: number;
  user_id: string;
  run_id: string;
  strategy_id: string;
  symbol: string;
  side?: "LONG" | "SHORT" | null;
  quantity: number;
  avg_entry_price: number;
  tp_price?: number | null;
  sl_price?: number | null;
  status?: "OPEN" | "CLOSED" | null;
  unrealized_pnl: number;
  realized_pnl?: number | null;
  exit_reason?: "TAKE_PROFIT" | "STOP_LOSS" | "MODEL_SELL" | null;
  exit_price?: number | null;
  opened_at?: string | null;
  closed_at?: string | null;
  paper_mode: boolean;
  snapshot_at: string;
  created_at?: string | null;
}

interface SignalEventDTO {
  id?: number;
  user_id: string;
  run_id: string;
  strategy_id: string;
  symbol: string;
  signal_action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  price_hint?: number | null;
  correlation_id: string;
  paper_mode: boolean;
  event_at: string;
  timeframe?: string | null;
  model_version?: string | null;
  created_at?: string | null;
}

interface ModelInferenceEventDTO {
  id?: number;
  user_id: string;
  run_id: string;
  strategy_id: string;
  symbol: string;
  model_version: string;
  feature_set_version: string;
  input_snapshot: Record<string, unknown>;   // MarketSnapshot
  output_prediction: Record<string, unknown>; // action, confidence 등
  paper_mode: boolean;
  inference_at: string;
  created_at?: string | null;
}

interface OrderRequestDTO {
  id?: number;
  user_id: string;
  run_id: string;
  strategy_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  order_type: "MARKET" | "LIMIT";
  quantity: number;
  price?: number | null;
  stop_price?: number | null;
  reduce_only: boolean;
  position_side: "BOTH" | "LONG" | "SHORT";
  correlation_id: string;
  paper_mode: boolean;
  requested_at: string;
  order_id?: string | null;
  client_order_id?: string | null;
  created_at?: string | null;
}

interface OrderExecutionDTO {
  id?: number;
  user_id: string;
  order_request_id?: number | null;
  run_id: string;
  strategy_id: string;
  symbol: string;
  order_id: string;
  status: string;           // FILLED 등
  executed_price?: number | null;
  executed_qty: number;
  stop_price?: number | null;
  reduce_only: boolean;
  position_side: string;
  raw_response?: Record<string, unknown> | null;
  paper_mode: boolean;
  executed_at: string;
  created_at?: string | null;
}

interface AuditLogDTO {
  id?: number;
  user_id: string;
  run_id: string;
  correlation_id: string;
  event: string;            // risk_rejected 등
  data: Record<string, unknown>;
  paper_mode: boolean;
  created_at?: string | null;
}

// ── API 복합 DTO ──────────────────────────────────────────

interface OrderFlowDTO {
  request: OrderRequestDTO;
  executions: OrderExecutionDTO[];
}

interface FlowTimelineItemDTO {
  event_type: "inference" | "signal" | "order_request" | "order_execution" | "position" | "audit";
  event_at: string;
  run_id: string;
  symbol?: string | null;
  summary: string;          // UI 한 줄 요약 (그대로 표시 가능)
  correlation_id?: string | null;
  payload: Record<string, unknown>;  // event_type별 상세 DTO
}

interface DashboardSummaryDTO {
  user_id: string;
  latest_run?: EngineRunDTO | null;
  open_positions: PositionSnapshotDTO[];
  closed_positions_today: number;
  realized_pnl_today: number;
  recent_timeline: FlowTimelineItemDTO[];
}
```

---

## 5. 응답 예시

### Dashboard

```json
{
  "user_id": "default",
  "latest_run": {
    "run_id": "testnet_timesfm_run",
    "strategy_id": "timesfm_consecutive_long_only",
    "model_version": "timesfm-2.5-200m",
    "feature_set_version": "price-history-v1",
    "version": "1.0.0",
    "paper_mode": false,
    "status": "running",
    "started_at": "2026-07-02T05:00:00+00:00",
    "stopped_at": null,
    "user_id": "default"
  },
  "open_positions": [
    {
      "symbol": "BTCUSDT",
      "side": "LONG",
      "status": "OPEN",
      "quantity": 0.002,
      "avg_entry_price": 97200.0,
      "tp_price": 98172.0,
      "sl_price": 96714.0,
      "unrealized_pnl": 0.42,
      "run_id": "testnet_timesfm_run",
      "strategy_id": "timesfm_consecutive_long_only",
      "paper_mode": false,
      "snapshot_at": "2026-07-02T05:32:00+00:00",
      "user_id": "default"
    }
  ],
  "closed_positions_today": 1,
  "realized_pnl_today": 12.5,
  "recent_timeline": [
    {
      "event_type": "signal",
      "event_at": "2026-07-02T05:32:00+00:00",
      "run_id": "testnet_timesfm_run",
      "symbol": "BTCUSDT",
      "summary": "Signal BUY conf=0.71",
      "correlation_id": "abc-123",
      "payload": { "signal_action": "BUY", "confidence": 0.71 }
    }
  ]
}
```

### Timeline item (payload 확장)

```json
{
  "event_type": "order_request",
  "event_at": "2026-07-02T05:33:00+00:00",
  "run_id": "testnet_timesfm_run",
  "symbol": "BTCUSDT",
  "summary": "Order BUY 0.002 BTCUSDT (MARKET)",
  "correlation_id": "abc-123",
  "payload": {
    "request": {
      "side": "BUY",
      "order_type": "MARKET",
      "quantity": 0.002,
      "symbol": "BTCUSDT"
    },
    "executions": [
      {
        "status": "FILLED",
        "executed_price": 97210.0,
        "executed_qty": 0.002
      }
    ]
  }
}
```

---

## 6. 프론트 구현 팁

1. **MVP:** Page 1(대시보드) + Page 2(타임라인)만으로 충분
2. **Polling:** `setInterval(() => fetch('/api/v1/dashboard?...'), 5000)`
3. **색상 가이드**
   - BUY / OPEN / TAKE_PROFIT → green
   - SELL / STOP_LOSS → red
   - HOLD → gray
   - audit `risk_rejected` → orange
4. **CORS:** 프론트 origin을 config `api.cors_origins`에 추가
5. **데이터 없음:** 엔진 미실행 시 `items: []`, `latest_run: null` — empty state UI 필요

---

## 7. 매매 흐름 (UI 이해용)

```text
inference (TimesFM) → signal (BUY/SELL/HOLD)
  → [BUY 3연속] → order_request → order_execution → position OPEN
  → [TP/SL/SELL 3연속] → order_request → order_execution → position CLOSED
  → audit (리스크 거부 등)
```

현재 전략: **long_only** (SELL = 숏 진입 아님, 롱 청산 신호)
