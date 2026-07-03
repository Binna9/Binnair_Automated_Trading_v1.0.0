# BinnAIR Monitor API — 전체 레퍼런스

> **read-only** API. 엔진 start/stop, 주문 제어 없음.  
> DB 이력 조회 + 거래소(testnet) 지갑 조회만 제공한다.

---

## 1. 기본 정보

| 항목 | 값 |
|------|-----|
| 실행 | `py scripts/run_api.py` |
| Base URL | `http://127.0.0.1:8000` (`config.yaml` → `api.host` / `api.port`) |
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| HTTP Method | **GET only** |
| 인증 | 없음 (v1) |
| Content-Type | `application/json` |
| datetime 형식 | ISO 8601 (예: `2026-07-03T08:00:00+00:00`) |
| date 형식 | `YYYY-MM-DD` |

### 공통 Query Parameters

대부분의 DB 조회 API에서 사용한다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `user_id` | string | `default` | 사용자별 이력 필터 |
| `run_id` | string | — | 엔진 실행 세션 ID (`config.run_context.run_id`) |
| `symbol` | string | — | 거래 심볼 (예: `XRPUSDT`, `BTCUSDT`) |
| `limit` | int | 엔드포인트별 | 조회 건수 상한 |

### 목록 응답 공통 형태

```json
{
  "items": [ ... ],
  "count": 0
}
```

---

## 2. 엔드포인트 목록

| # | Method | Path | 데이터 소스 | 설명 |
|---|--------|------|-------------|------|
| 1 | GET | `/health` | 서버 | 헬스체크 |
| 2 | GET | `/api/v1/dashboard` | Postgres | 대시보드 요약 |
| 3 | GET | `/api/v1/account/wallet` | Binance API | testnet 지갑·sizing 진단 |
| 4 | GET | `/api/v1/engine-runs` | Postgres | 엔진 실행 세션 목록 |
| 5 | GET | `/api/v1/engine-runs/{run_id}` | Postgres | 실행 세션 상세 |
| 6 | GET | `/api/v1/positions/open` | Postgres | 현재 OPEN 포지션 |
| 7 | GET | `/api/v1/positions` | Postgres | 포지션 스냅샷 이력 |
| 8 | GET | `/api/v1/signals` | Postgres | BUY/SELL/HOLD 시그널 |
| 9 | GET | `/api/v1/inferences` | Postgres | TimesFM 추론 이벤트 |
| 10 | GET | `/api/v1/orders` | Postgres | 주문 요청 + 체결 |
| 11 | GET | `/api/v1/audit-logs` | Postgres | 감사/리스크 로그 |
| 12 | GET | `/api/v1/flow/timeline` | Postgres | 매매 흐름 타임라인 |
| 13 | GET | `/api/v1/performance/summary` | Postgres | 성과 요약 (승률·PnL) |
| 14 | GET | `/api/v1/performance/periods` | Postgres | 일/주/월 성과 시계열 |
| 15 | GET | `/api/v1/performance/trades` | Postgres | 청산 거래 목록 |

---

## 3. 엔드포인트 상세

### 3.1 `GET /health`

서버 생존 확인.

**Response**

```json
{ "status": "ok" }
```

---

### 3.2 `GET /api/v1/dashboard`

메인 대시보드용 요약. 최신 run, OPEN 포지션, 오늘 실현손익, 최근 타임라인을 한 번에 반환한다.

**Query**

| 파라미터 | 필수 | 설명 |
|----------|------|------|
| `user_id` | | 사용자 ID |
| `run_id` | | 미지정 시 최신 run 기준 |
| `symbol` | | 심볼 필터 |

**예시**

```
GET /api/v1/dashboard?user_id=default&run_id=testnet_timesfm_run&symbol=XRPUSDT
```

**Response 필드**

| 필드 | 설명 |
|------|------|
| `latest_run` | 최근 `engine_run` (status, started_at 등) |
| `open_positions` | OPEN `position_snapshot` 목록 |
| `closed_positions_today` | 오늘(UTC) 청산 건수 |
| `realized_pnl_today` | 오늘 청산 포지션 `realized_pnl` 합계 |
| `recent_timeline` | 최근 매매 흐름 15건 (`FlowTimelineItemDTO`) |

---

### 3.3 `GET /api/v1/account/wallet`

`config.yaml`의 `exchange` 설정(API 키, testnet URL)으로 **Binance Futures testnet** 지갑을 실시간 조회한다.  
엔진 sizing에 쓰는 USDT 잔고와 주문 가능 여부를 진단할 때 사용한다.

**Query** — 없음 (config 기준)

**예시**

```
GET /api/v1/account/wallet
```

**Response 필드**

| 필드 | 설명 |
|------|------|
| `ok` | 조회 성공 여부 |
| `paper_mode` | 종이거래 모드 여부 |
| `base_url` | 거래소 URL (testnet) |
| `balances` | 자산별 잔고 (USDT, BTC 등) |
| `account` | `available_balance`, `total_wallet_balance`, `can_trade` 등 |
| `positions` | 거래소 선물 포지션 (현재 계정 기준) |
| `engine_diagnostics` | 엔진 sizing 진단 |
| `engine_diagnostics.available_balance` | USDT available |
| `engine_diagnostics.can_create_order` | BUY 신호 시 주문 가능 여부 |
| `engine_diagnostics.sizing_result` | 샘플 가격 기준 예상 수량/명목 |
| `error` | API 키 오류, 연결 실패 시 |

> **주의:** run_id별 데이터가 아니라 **계정 전체** 지갑이다. DB run과 별개.

---

### 3.4 `GET /api/v1/engine-runs`

엔진 실행 세션 목록.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `status` | — | `running` \| `stopped` \| `error` |
| `limit` | `20` | 1~200 |

**예시**

```
GET /api/v1/engine-runs?user_id=default&status=running&limit=10
```

---

### 3.5 `GET /api/v1/engine-runs/{run_id}`

특정 실행 세션 상세.

**Path**

| 파라미터 | 설명 |
|----------|------|
| `run_id` | 예: `testnet_timesfm_run` |

**에러**

- `404` — run_id 없음

**예시**

```
GET /api/v1/engine-runs/testnet_timesfm_run?user_id=default
```

---

### 3.6 `GET /api/v1/positions/open`

현재 보유 중(OPEN) 포지션만 조회. run_id 무관, 심볼별 최신 OPEN 스냅샷.

**Query**

| 파라미터 | 설명 |
|----------|------|
| `user_id` | |
| `symbol` | 특정 심볼만 |

**예시**

```
GET /api/v1/positions/open?user_id=default&symbol=XRPUSDT
```

---

### 3.7 `GET /api/v1/positions`

포지션 스냅샷 전체 이력 (OPEN / CLOSED).

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `symbol` | — | |
| `status` | — | `OPEN` \| `CLOSED` |
| `limit` | `50` | 1~500 |

**CLOSED 행 주요 필드**

| 필드 | 설명 |
|------|------|
| `realized_pnl` | 실현 손익 (USDT) |
| `exit_price` | 청산가 |
| `exit_reason` | `TAKE_PROFIT` \| `STOP_LOSS` \| `MODEL_SELL` |

**예시**

```
GET /api/v1/positions?run_id=testnet_timesfm_run&status=CLOSED&limit=20
```

---

### 3.8 `GET /api/v1/signals`

Predictor/Strategy가 기록한 BUY / SELL / HOLD 시그널.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `symbol` | — | |
| `limit` | `100` | 1~500 |

**주요 필드:** `signal_action`, `confidence`, `correlation_id`, `event_at`

**예시**

```
GET /api/v1/signals?run_id=testnet_timesfm_run&symbol=XRPUSDT&limit=50
```

---

### 3.9 `GET /api/v1/inferences`

TimesFM 모델 추론 이벤트 (BUY/SELL 시 저장).

**Query** — `signals`와 동일

**주요 필드:** `input_snapshot`, `output_prediction` (action, confidence, score 등)

**예시**

```
GET /api/v1/inferences?run_id=testnet_timesfm_run&limit=30
```

---

### 3.10 `GET /api/v1/orders`

주문 요청(`order_request`)과 체결(`order_execution`)을 묶어서 반환.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `symbol` | — | |
| `limit` | `50` | 1~200 |

**Response item 구조**

```json
{
  "request": { "side": "BUY", "order_type": "MARKET", "quantity": 1000, ... },
  "executions": [ { "status": "FILLED", "executed_price": 1.02, ... } ]
}
```

**예시**

```
GET /api/v1/orders?run_id=testnet_timesfm_run&symbol=XRPUSDT
```

---

### 3.11 `GET /api/v1/audit-logs`

리스크 거부, 포지션 청산 등 감사 이벤트.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `limit` | `100` | 1~500 |

**주요 event:** `risk_rejected`, `position_closed` 등

**예시**

```
GET /api/v1/audit-logs?run_id=testnet_timesfm_run&limit=50
```

---

### 3.12 `GET /api/v1/flow/timeline`

추론 → 시그널 → 주문 → 체결 → 포지션 → 감사 로그를 **시간순 한 줄 요약**으로 합친 타임라인.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `symbol` | — | |
| `limit` | `100` | 1~500 |

**event_type**

| 값 | 의미 |
|----|------|
| `inference` | TimesFM 추론 |
| `signal` | BUY/SELL/HOLD |
| `order_request` | 주문 요청 |
| `order_execution` | 체결 |
| `position` | 포지션 OPEN/CLOSED |
| `audit` | 감사/리스크 |

`correlation_id`로 같은 tick 이벤트를 UI에서 그룹핑할 수 있다.

**예시**

```
GET /api/v1/flow/timeline?run_id=testnet_timesfm_run&symbol=XRPUSDT&limit=100
```

---

### 3.13 `GET /api/v1/performance/summary`

**청산 완료 거래(`trade_result`)** 기준 기간 성과 요약. 승률·손익·수익률을 한 번에 본다.

**Query**

| 파라미터 | 설명 |
|----------|------|
| `user_id` | |
| `run_id` | run별 필터 (수익률 % 계산에 필요) |
| `symbol` | 심볼 필터 |
| `from_at` | ISO8601 시작 (예: `2026-07-01T00:00:00Z`) |
| `to_at` | ISO8601 종료 |

**예시**

```
GET /api/v1/performance/summary?run_id=testnet_timesfm_run
GET /api/v1/performance/summary?run_id=testnet_timesfm_run&from_at=2026-07-01T00:00:00Z&to_at=2026-07-31T23:59:59Z
```

**Response 필드**

| 필드 | 설명 |
|------|------|
| `total_trades` | 청산 거래 수 |
| `win_count` / `loss_count` / `breakeven_count` | 승 / 패 / 무 |
| `win_rate` | `win_count / total_trades` (0~1) |
| `realized_pnl_total` | 기간 실현손익 합 (USDT) |
| `avg_pnl_per_trade` | 거래당 평균 손익 |
| `avg_pnl_pct` | 거래당 평균 수익률 (%) |
| `gross_profit` / `gross_loss` | 이익 합 / 손실 절대값 합 |
| `profit_factor` | `gross_profit / gross_loss` |
| `best_trade_pnl` / `worst_trade_pnl` | 최대 이익 / 최대 손실 거래 |
| `return_pct` | `realized_pnl_total / reference_equity × 100` |
| `reference_equity_usdt` | 엔진 시작 시 `equity_snapshot` 잔고 |

> 청산 이력이 없으면 모든 값 0 / null.

---

### 3.14 `GET /api/v1/performance/periods`

일 / 주 / 월 단위 성과 시계열.

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `granularity` | `day` | `day` \| `week` \| `month` |
| `from_date` | — | `YYYY-MM-DD` |
| `to_date` | — | `YYYY-MM-DD` |
| `limit` | `90` | 1~366 |

**예시**

```
GET /api/v1/performance/periods?run_id=testnet_timesfm_run&granularity=day
GET /api/v1/performance/periods?run_id=testnet_timesfm_run&granularity=month&from_date=2026-01-01
```

**Response**

```json
{
  "granularity": "day",
  "items": [
    {
      "period_start": "2026-07-03",
      "period_label": "2026-07-03",
      "trade_count": 2,
      "win_count": 1,
      "loss_count": 1,
      "win_rate": 0.5,
      "realized_pnl_sum": 12.5,
      "avg_pnl_pct": 0.8,
      "return_pct": 0.25,
      "opening_equity_usdt": 5000.0,
      "closing_equity_usdt": 5012.5
    }
  ],
  "count": 1
}
```

| granularity | period_label 예시 |
|-------------|-------------------|
| `day` | `2026-07-03` |
| `week` | `2026-W27` |
| `month` | `2026-07` |

- `granularity=day` → `performance_daily` 테이블 (일 시작 잔고·수익률 포함)
- `week` / `month` → `trade_result` 집계 (`return_pct`는 null)

---

### 3.15 `GET /api/v1/performance/trades`

청산 완료 거래 1건 = 1 row (`trade_result` 테이블).

**Query**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `user_id` | `default` | |
| `run_id` | — | |
| `symbol` | — | |
| `from_at` | — | ISO8601 |
| `to_at` | — | ISO8601 |
| `limit` | `100` | 1~500 |

**예시**

```
GET /api/v1/performance/trades?run_id=testnet_timesfm_run&symbol=XRPUSDT&limit=50
```

**주요 필드**

| 필드 | 설명 |
|------|------|
| `trade_id` | 거래 UUID |
| `side` | `LONG` \| `SHORT` |
| `entry_price` / `exit_price` | 진입가 / 청산가 |
| `quantity` | 체결 수량 |
| `realized_pnl` | 실현 손익 (USDT) |
| `pnl_pct` | 거래 수익률 (%) |
| `is_win` | 승리 여부 |
| `exit_reason` | `TAKE_PROFIT` \| `STOP_LOSS` \| `MODEL_SELL` |
| `opened_at` / `closed_at` | 진입·청산 시각 |
| `hold_seconds` | 보유 시간(초) |

---

## 4. 데이터 흐름 (참고)

```text
[엔진 tick]
  → inference (TimesFM)
  → signal (BUY/SELL/HOLD)
  → order_request → order_execution
  → position_snapshot (OPEN)
  → [TP/SL/SELL 청산]
  → position_snapshot (CLOSED)
  → trade_result + performance_daily (자동 기록)

[엔진 start]
  → engine_run
  → equity_snapshot (시작 잔고 → 수익률 % 분모)
```

### 관련 DB 테이블

| 테이블 | API에서 사용 |
|--------|-------------|
| `engine_run` | engine-runs, dashboard |
| `position_snapshot` | positions, dashboard |
| `signal_event` | signals, timeline |
| `model_inference_event` | inferences, timeline |
| `order_request` / `order_execution` | orders, timeline |
| `audit_log` | audit-logs, timeline |
| `trade_result` | performance/* |
| `performance_daily` | performance/periods (day) |
| `equity_snapshot` | performance/summary (return_pct) |

---

## 5. 빠른 테스트 (curl)

```bash
# 헬스
curl http://127.0.0.1:8000/health

# 대시보드
curl "http://127.0.0.1:8000/api/v1/dashboard?run_id=testnet_timesfm_run&symbol=XRPUSDT"

# testnet 지갑
curl http://127.0.0.1:8000/api/v1/account/wallet

# 성과 요약
curl "http://127.0.0.1:8000/api/v1/performance/summary?run_id=testnet_timesfm_run"

# 월별 성과
curl "http://127.0.0.1:8000/api/v1/performance/periods?run_id=testnet_timesfm_run&granularity=month"

# 타임라인
curl "http://127.0.0.1:8000/api/v1/flow/timeline?run_id=testnet_timesfm_run&limit=30"
```

---

## 6. 관련 문서

- [API_FRONTEND.md](./API_FRONTEND.md) — 프론트 화면 구성·DTO TypeScript·UI 팁
- [config/config.yaml](../config/config.yaml) — `api`, `exchange`, `run_context` 설정
