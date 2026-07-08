# BinnAIR Monitor API — 전체 레퍼런스

> **read-only** HTTP API + **실시간 WebSocket**. 엔진 start/stop, 주문 제어 없음.  
> DB 이력(REST) + 거래소 지갑·포지션(**WebSocket**, REST 스냅샷) 제공.

**실시간 연동:** 3.3b절 `/ws/v1/live` 참조 (별도 문서로 분리되어 있지 않음).

---

## 1. 기본 정보

| 항목 | 값 |
|------|-----|
| 실행 | `py scripts/run_api.py` |
| Base URL | 로컬 `http://127.0.0.1:8000` (`.env.dev`) / 서버 `http://127.0.0.1:8001`(`trade.env`, 컨테이너 내부 바인딩 — 외부 노출은 리버스 프록시 경로에 따름) |
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| HTTP Method | **GET only** (WebSocket 별도) |
| WebSocket | `ws://127.0.0.1:8000/ws/v1/live` — 3.3b절 참조 |
| 인증 | 없음 (v1) |
| Content-Type | `application/json` |
| datetime 형식 | ISO 8601 (예: `2026-07-03T08:00:00+00:00`) |
| date 형식 | `YYYY-MM-DD` |

### 공통 Query Parameters

대부분의 DB 조회 API에서 사용한다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `user_id` | string | `default` | 사용자별 이력 필터 |
| `run_id` | string | — | 엔진 실행 세션 ID (`config.run_context.run_id`). 아래 예시의 `testnet_timesfm_run`은 로컬/테스트넷 기준 예시값이며, 실제 값은 환경별 `BINNAIR_RUN_ID` 설정을 따른다 (예: 운영 `prod_timesfm_run`) |
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
| 3 | GET | `/api/v1/account/wallet` | Binance REST | 지갑 스냅샷·sizing 진단 (WS 폴백) |
| 3b | GET | `/api/v1/live/status` | 서버 | WebSocket 브리지 연결 상태 |
| 3c | WS | `/ws/v1/live` | Binance WS | **실시간** 지갑·포지션·체결 — 3.3b절 참조 |
| 3d | GET | `/api/v1/autopilot/status` | JSON 파일 | Autopilot 레짐·threshold·TP/SL 진화 상태 |
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
| **16** | GET | **`/api/v1/history/summary`** | Postgres | **엔진 이력 요약 (권장)** |
| **17** | GET | **`/api/v1/history/orders`** | Postgres | **주문 내역** |
| **18** | GET | **`/api/v1/history/executions`** | Postgres | **체결( fill ) 내역** |
| **19** | GET | **`/api/v1/history/positions`** | Postgres | **포지션 내역** |
| **20** | GET | **`/api/v1/history/trades`** | Postgres | **청산 거래 (라운드트rip)** |
| **21** | GET | **`/api/v1/history`** | Postgres | **통합 조회 (summary + 최근 N건)** |

> **프론트 "내역" 화면**은 `/history/*` 사용 권장. 기존 `/orders`, `/positions`, `/performance/trades`는 하위 호환.

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

`BINNAIR_EXCHANGE_*` 환경변수로 **Binance Futures** 지갑을 조회한다 (testnet/mainnet은 `BINNAIR_EXCHANGE_BASE_URL`로 구분).  
**실시간 갱신은 WebSocket `/ws/v1/live` 사용.** 이 REST는 초기 로딩·폴백용.

**Query** — 없음 (config 기준)

**예시**

```
GET /api/v1/account/wallet
```

**Response 필드**

| 필드 | 설명 |
|------|------|
| `ok` | 조회 성공 여부 |
| `environment` | `futures_testnet` \| `futures_mainnet` \| `paper` |
| `paper_mode` | 종이거래 모드 여부 |
| `base_url` | 거래소 REST URL |
| `stream` | WebSocket 베이스 URL·구독 채널 힌트 |
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

### 3.3a `GET /api/v1/live/status`

WebSocket 브리지(`BinanceLiveBridge`) 연결 상태만 조회. 스트림 데이터 자체는 아래 3.3b `/ws/v1/live`로 받는다.

**Response**

```json
{ "ok": true, "user_stream_connected": true, "mark_price_connected": true, "last_error": null, "client_count": 1, "has_snapshot": true }
```

---

### 3.3b `WS /ws/v1/live`

Binance User Data Stream(지갑/포지션/체결) + mark price 스트림을 그대로 클라이언트에 fan-out하는 실시간 WebSocket. `api/controllers/ws_controller.py`, `api/services/live_hub.py`/`live_bridge.py` 구현.

**연결**

```
ws://127.0.0.1:8000/ws/v1/live?symbol=XRPUSDT
```

`symbol`은 선택 — 미지정 시 `config.market_data.symbol` 기준.

**연결 직후 서버 → 클라이언트**

1. 최근 캐시된 스냅샷 (`{"wallet": {...}, "positions": [...], "mark_prices": {...}}`) — 있는 경우
2. `{"type": "stream_status", "user_stream_connected": ..., "mark_price_connected": ..., "client_count": ...}`

**이후 push되는 message.type**

| type | 의미 |
|------|------|
| `wallet_update` | 지갑 잔고 변경 (`balances: [{asset, wallet_balance, cross_wallet_balance}, ...]`) |
| `position_update` | 포지션 변경 (`symbol, side, quantity, entry_price, unrealized_pnl, margin_type`) |
| `position_closed` | 포지션 청산 (해당 symbol을 캐시에서 제거) |
| `mark_price` | mark price 갱신 (`symbol, mark_price`) |
| `stream_status` | 연결 상태 변경 시 재전송 |
| `ping` | 30초 keepalive |

**클라이언트 → 서버**: `{"action": "refresh"}` 전송 시 REST 스냅샷 재조회를 트리거할 수 있다 (연결 유지용 텍스트 프레임을 기대하므로 완전히 무응답 연결은 피할 것).

> 서버가 유지하는 최신 스냅샷은 신규 접속 클라이언트에게 즉시 재전송하기 위한 캐시이며, `apply_message()`가 락 안에서 `_merge_state_locked()`로 갱신한다.

---

### 3.3c `GET /api/v1/autopilot/status`

Autopilot(레짐 감지·adaptive threshold·ATR TP/SL) 현재 상태. **DB가 아니라** 엔진이 tick마다 쓰는 `autopilot_state.json`(`BINNAIR_STATE_PERSIST_PATH`와 같은 폴더)을 읽는다 — 조회 시점 엔진 프로세스가 최근에 tick을 돌렸어야 값이 있다.

**Query**

| 파라미터 | 필수 | 설명 |
|----------|------|------|
| `run_id` | | 지정 시 저장된 state의 run_id와 일치해야 `available: true` |

**예시**

```
GET /api/v1/autopilot/status?run_id=prod_timesfm_run
```

**Response 필드**

| 필드 | 설명 |
|------|------|
| `enabled` | Autopilot 활성 여부 (`BINNAIR_AUTOPILOT_ENABLED`) |
| `available` | state 파일 존재 + run_id 일치 여부 |
| `regime` | `unknown` \| `normal` \| `high_vol` \| `low_vol` \| `ranging` \| `trending` |
| `atr` / `atr_pct` | True Range 기반 ATR (절대값 / 가격 대비 %) |
| `trend_slope` | EMA fast/slow 기울기 (가격 대비) |
| `base_threshold` / `regime_threshold_mult` / `effective_threshold` | adaptive threshold 계산 과정 (`base × 배수 = effective`) |
| `fee_floor` / `min_threshold` | 수수료+슬리피지 원가 참고값 / 실제 하한(설정된 signal_threshold 또는 fee_floor) |
| `score_samples` | 현재 calibrator에 쌓인 |score| 샘플 수 |
| `consecutive_required` | 현재 tick에 적용 중인 연속 신호 확인 횟수 |
| `tp_pct` / `sl_pct` / `tp_atr_mult` / `sl_atr_mult` | 현재 ATR 기반 TP/SL % 및 배수 |
| `position_scale` | 고변동성 레짐에서 포지션 축소 비율 (0.1~1.0) |
| `state_path` | 읽은 JSON 파일 경로 |

state 파일이 없거나 run_id가 다르면 `available: false`와 `message`만 반환한다 (엔진 미기동, 또는 재기동 직후 첫 tick 전).

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
| `exit_reason` | `TAKE_PROFIT` \| `STOP_LOSS` \| `MODEL_SELL` \| `SHUTDOWN` \| `EXCHANGE_SYNC` |

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

**주요 event:** `risk_rejected`(연속 손절 서킷브레이커 발동 시 `reason`에 `consecutive_loss_pause` 포함), `position_closed`, `position_reconciled`(거래소 동기화 중 강제 정리) 등

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
| `exit_reason` | `TAKE_PROFIT` \| `STOP_LOSS` \| `MODEL_SELL` \| `SHUTDOWN` \| `EXCHANGE_SYNC` |
| `opened_at` / `closed_at` | 진입·청산 시각 |
| `hold_seconds` | 보유 시간(초) |

---

## 3.16 엔진 이력 API (`/api/v1/history/*`)

엔진이 DB에 기록한 **주문·체결·포지션·청산 거래**를 프론트 "내역" 탭 단위로 제공한다.  
모든 엔드포인트에 `run_id` 지정을 권장한다 (`config.run_context.run_id`).

### 공통 Query

| 파라미터 | 설명 |
|----------|------|
| `user_id` | 기본 `default` |
| `run_id` | 엔진 실행 ID |
| `symbol` | 예: `XRPUSDT` |
| `from_at` / `to_at` | ISO8601 기간 (KST 저장) |
| `limit` | 목록 상한 |

### `GET /api/v1/history/summary`

현재 run 기준 카운트·최근 활동 시각·실현손익 합계.

```
GET /api/v1/history/summary?run_id=testnet_timesfm_run&symbol=XRPUSDT
```

| 필드 | 설명 |
|------|------|
| `open_positions` | 현재 OPEN (심볼별 최신 1건) |
| `orders_total` / `orders_filled` / `orders_pending` | 주문 건수 |
| `executions_total` | 체결 건수 |
| `closed_positions` / `closed_trades` | CLOSED 스냅샷 / trade_result |
| `realized_pnl_sum` | 기간 내 청산 PnL 합 |
| `latest_*_at` | 최근 signal/order/execution/position 시각 |

### `GET /api/v1/history/orders`

**주문 내역** — `order_request` + 체결 요약.

추가 Query: `side` (BUY\|SELL), `fill_status` (PENDING\|FILLED\|REJECTED\|CANCELLED)

| 필드 | 설명 |
|------|------|
| `fill_status` | PENDING=order_id만 있음, FILLED=체결됨, REJECTED=order_id 없음 |
| `filled_qty` / `avg_fill_price` / `executed_at` | 체결 정보 (없으면 null) |
| `reduce_only` | 청산 주문 여부 |

> **주의:** `signal_event` BUY와 다름. 신호만 있고 주문 없으면 이 API에 안 나온다.

### `GET /api/v1/history/executions`

**체결 내역** — `order_execution` flat 목록.

| 필드 | 설명 |
|------|------|
| `executed_qty` / `executed_price` | 체결 수량·가격 |
| `notional_usdt` | price × qty |
| `status` | 거래소 체결 상태 (보통 FILLED) |

### `GET /api/v1/history/positions`

**포지션 내역** — `position_snapshot`.

추가 Query: `status` (OPEN\|CLOSED), `open_only=true` (심볼별 최신 OPEN 1건)

| status | 의미 |
|--------|------|
| OPEN | 진입 시점 (TP/SL, unrealized_pnl) |
| CLOSED | 청산 시점 (realized_pnl, exit_reason, duration_seconds) |

### `GET /api/v1/history/trades`

**청산 완료 거래** — `trade_result` (진입→청산 1라운드).

`/performance/trades`와 동일 데이터, `holding_seconds` 필드 추가.

### `GET /api/v1/history`

대시보드용 **통합 조회**. `run_id` **필수**. summary + orders/executions/positions/trades 각 `recent_limit`건.

```
GET /api/v1/history?run_id=testnet_timesfm_run&recent_limit=20
```

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
| `order_request` / `order_execution` | orders, timeline, **history/orders, history/executions** |
| `audit_log` | audit-logs, timeline |
| `trade_result` | performance/*, **history/trades** |
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

# 엔진 이력 (권장)
curl "http://127.0.0.1:8000/api/v1/history/summary?run_id=testnet_timesfm_run"
curl "http://127.0.0.1:8000/api/v1/history/orders?run_id=testnet_timesfm_run&limit=20"
curl "http://127.0.0.1:8000/api/v1/history/executions?run_id=testnet_timesfm_run"
curl "http://127.0.0.1:8000/api/v1/history/positions?run_id=testnet_timesfm_run&status=CLOSED"
curl "http://127.0.0.1:8000/api/v1/history/trades?run_id=testnet_timesfm_run"
curl "http://127.0.0.1:8000/api/v1/history?run_id=testnet_timesfm_run&recent_limit=10"
```

---

## 6. 관련 문서

- [README.md](../README.md) — 엔진 아키텍처, 모듈 구조, 실행 방법
- [PERSISTENCE.md](./PERSISTENCE.md) — DB 테이블, DTO, Repository 상세
- `.env.dev` (로컬, gitignore) / `trade.env` (서버, gitignore) — `BINNAIR_*` 설정. 프론트 전용 문서(API_FRONTEND.md)는 아직 작성되지 않음.
