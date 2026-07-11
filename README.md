# BinnAIR Automated Trading Engine

TimesFM 예측 기반 자동매매 엔진 (Binance USD-M Futures). Paper trading 겸용, 엔진/API 분리 구조.

---

## 구현 현황 (Implementation Status)

### ✅ 완료된 기능

| 영역 | 구현 내용 | 비고 |
|------|-----------|------|
| **진입** | Predictor → Signal → Strategy → Risk → Exchange 주문 | BUY 연속 N회 시 TP/SL 계산 후 진입, position_snapshot 저장 |
| **보유** | 포지션 유지, TP/SL 매 tick 감시 | Autopilot 활성 시 ATR 기반 TP/SL을 tick마다 재계산 |
| **청산 (가격 기반)** | ExitManager TP/SL 도달 시 SELL | TAKE_PROFIT / STOP_LOSS 구분 저장, 가격 조건은 항상 최우선 |
| **청산 (신호 기반)** | 모델 SELL 연속 N회 시 롱 청산 | `MODEL_SELL`. 단, 진입 후 `min_hold_seconds_before_signal_exit`(기본 90초) 전에는 보류 — TP/SL은 예외 없이 즉시 적용 |
| **재기동** | DB `position_snapshot` OPEN 포지션 복구 + 거래소 포지션 양방향 동기화 | `_recover_positions_from_db`, `_sync_position_with_exchange` |
| **Autopilot** | 레짐(추세/변동성) 감지 → threshold·TP/SL·consecutive_required 자동 조정 | `autopilot/` — score 분포 기반 adaptive threshold, OHLC High/Low 기반 True Range ATR |
| **리스크 관리** | 일손실 제한, 포지션/명목 한도, 중복주문 방지, **연속 손절 서킷브레이커** | N회 연속 손절 시 일정 시간 신규 진입 차단 |
| **실시간 스트림** | Binance User Data Stream → WebSocket 브리지 | `/ws/v1/live` — 지갑·포지션·체결 push |
| **Web API** | FastAPI read-only REST (이력/성과/대시보드/오토파일럿 상태) | 상세: [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |
| **Persistence** | 13개 테이블 (ohlcv_candle ~ equity_snapshot) | PostgreSQL + `init_db.py`. 상세: [docs/PERSISTENCE.md](docs/PERSISTENCE.md) |
| **청산 결과 추적** | position_snapshot/trade_result에 exit_reason, exit_price, realized_pnl | 거래소측 임의 소멸(OCO 등) 시에도 TP/SL 가격 대비 best-effort 추정 |

### 🔶 부분 구현

| 영역 | 구현 내용 | 미구현 |
|------|-----------|--------|
| **Predictor** | TimesFM(zero-shot), Dummy, RuleBased | TimesFM은 DB OHLCV close 히스토리 기반. 재학습/파인튜닝 없음 |
| **Exchange** | Binance **Futures**(운영 기본), Spot, Paper | 거래소 네이티브 TP/SL 주문(`oco_enabled`)은 코드는 있으나 기본 비활성 — 로컬 폴링 기반 청산이 기본 경로 |
| **Storage** | memory / postgres 백엔드 | Redis, Alembic 마이그레이션 없음 (`init_db.py`로 스키마 관리) |
| **Market Data** | Binance REST OHLCV 폴링(`poll_interval_seconds`) | 시세 자체는 WebSocket 미사용 (User Data Stream만 WS) |

### ❌ 미구현

- Trailing stop, 부분 청산(partial exit)
- 선물 펀딩비(funding rate) 비용 반영
- 일별 PnL 집계 API는 있음(`/performance/periods`)이나 프론트 대시보드 시각화는 별도 저장소
- Redis 캐시
- Alembic 마이그레이션

---

## Quick Start (환경 구성)

**의존성 한 줄 설치** (가상환경 활성화 후 프로젝트 루트에서):

```bash
pip install -e .
```

전체 절차:

```bash
# 1. venv 생성 (Python 3.12)
python3.12 -m venv .venv

# 2. venv 활성화
# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -e .
```

**Poetry/uv 사용 시** (venv 자동 생성):

```bash
poetry install
# 또는
uv sync
```

---

## 디렉터리 구조

```
src/binnair_trading_engine/
├── app/                    # 부트스트랩 및 진입점
│   ├── bootstrap.py       # 설정 로드, DI, 엔진 인스턴스 생성
│   └── main.py            # CLI 진입점
├── autopilot/              # 적응형 threshold·TP/SL·레짐 감지
│   ├── controller.py      # AutopilotController: tick마다 threshold/TP-SL/consecutive 갱신
│   ├── calibration.py     # ThresholdCalibrator: score 분포 기반 adaptive threshold
│   ├── regime.py          # RegimeDetector: OHLC True Range ATR, EMA 추세, TP/SL 배수
│   ├── models.py          # AutopilotConfig, RegimeSnapshot, AutopilotState
│   └── persist.py         # autopilot_state.json persist/복구
├── config/                 # 설정
│   ├── settings.py        # EngineConfig 및 하위 dataclass (Risk/Sizing/Autopilot 등)
│   └── env_loader.py      # BINNAIR_* 환경변수 → EngineConfig
├── domain/                 # 도메인 모델 (엔진 내부 사용 객체)
│   └── models.py          # Signal, Order, Position, Trade, Prediction, MarketSnapshot 등
├── engine/                 # 엔진 코어
│   └── core.py            # TradingEngine: 진입/청산 흐름, process_tick, run_cycle
├── exchange/                # 거래소 어댑터
│   ├── interface.py       # ExchangeAdapter
│   ├── paper.py           # PaperExchangeAdapter (종이거래)
│   ├── binance_spot.py    # BinanceSpotAdapter
│   ├── binance_futures.py # BinanceFuturesAdapter (운영 기본, USD-M Futures)
│   ├── binance_listen_key.py    # User Data Stream listenKey 발급/keepalive
│   └── binance_stream_parser.py # WS 메시지 파싱
├── infra/                  # DB/Persistence 인프라
│   └── persistence/
│       ├── session.py     # DB Engine/Session (BINNAIR_STORAGE_* → to_database_url())
│       ├── models.py      # SQLAlchemy ORM (13개 테이블)
│       ├── dto.py         # Repository 입출력 DTO (*DTO 조회용, *Create 입력용)
│       └── repositories/
│           ├── interfaces.py  # Repository Protocol
│           └── postgres.py    # Postgres 구현체
├── market_data/             # 시세 수신
│   ├── interface.py       # MarketDataProvider
│   ├── history.py         # PriceHistoryProvider — close 시계열 + OHLC(high/low/close) 제공
│   ├── ohlcv_ingest.py     # OHLCV 캔들 적재
│   └── binance_rest.py    # Binance REST ticker/price 및 klines 조회
├── predictor/               # 추론/모델
│   ├── interface.py       # Predictor
│   ├── dummy.py           # DummyPredictor (테스트용)
│   ├── rule_based.py       # RuleBasedPredictor (가격 규칙)
│   └── timesfm_predictor.py # TimesFM 기반 zero-shot 예측, adaptive threshold
├── position/                # 포지션 관리
│   └── manager.py          # PositionManager: open/close, restore_from_snapshot
├── risk/                    # 리스크 관리
│   ├── checker.py          # RiskChecker (record_trade_result 훅 포함)
│   ├── default.py          # DefaultRiskChecker — 일손실/명목한도/중복주문 + 연속손절 서킷브레이커
│   ├── sizing.py           # PercentEquitySizingPolicy — 잔고·손절거리 기반 수량 계산
│   └── config.py           # 리스크 기본 상수
├── signal/                  # 모델 시그널 후처리 정책
│   └── policy.py            # ConsecutiveSignalPolicy (진입/청산 각각 연속 N회 확인)
├── storage/                  # 저장 레이어
│   ├── interface.py        # OrderStore, SignalStore, PositionStore 등
│   ├── postgres.py         # PostgresStorage (메모리, backend=memory)
│   └── postgres_db.py      # PostgresDbStorage (실제 DB, backend=postgres)
├── state/                    # 상태 관리 (장애 복구)
│   └── manager.py           # StateManager: start/stop/heartbeat, JSON 파일 persist
├── strategy/                 # 전략 및 청산
│   ├── interface.py         # Strategy
│   ├── passthrough.py       # PassthroughStrategy — 모델 예측을 TP/SL 주문 의도로 변환
│   └── exit_manager.py      # ExitManager (TP/SL 판단, 항상 최우선)
└── api/                       # FastAPI read-only REST + WebSocket 서버
    ├── main.py               # create_app(), CORS, 라우터 등록
    ├── controllers/          # flow(대시보드/성과), history, autopilot, ws
    ├── services/             # live_hub, live_bridge, wallet_service, autopilot_service, order_fill_resolver
    ├── repositories/         # history/performance/flow 조회 전용 Repository
    ├── dto/                  # API 응답 DTO
    └── common/               # db.py, mappers.py, parse.py, serialize.py

scripts/
├── init_db.py                    # DB 테이블 생성 및 마이그레이션
├── ingest_ohlcv.py                # Binance OHLCV 캔들 적재 (TimesFM 입력 히스토리)
├── run_engine.py                  # OHLCV 적재 + 매매 엔진 한 번에 실행
├── run_api.py                     # 조회 API 서버
└── download_timesfm_weights.py    # TimesFM 가중치 다운로드

.env.dev                 # 로컬 개발 설정 (gitignore, BINNAIR_*)
Dockerfile.engine / Dockerfile.api
.github/workflows/       # push to main → ghcr.io 이미지 빌드 (engine/api 각각)
```

> 운영 서버는 `binnair-stack/env/trade.env`(서버 전용, 이 리포에 없음)로 별도 배포되며, `compose.trading.yml`(리포 루트, `binnair-stack/compose.yml`에 붙여넣는 스니펫)로 컨테이너를 구성한다. `main` 브랜치 push는 이미지 빌드만 트리거하며, 서버에서 pull/재기동은 별도로 수행해야 한다.

---

## 모듈 역할

| 모듈 | 역할 |
|------|------|
| **app** | bootstrap: 설정 로드 → DI → TradingEngine. main: CLI 진입점 |
| **autopilot** | tick마다 시장 레짐(추세/변동성)을 감지해 진입 threshold, TP/SL(ATR 기반), consecutive_required를 자동 조정 |
| **config** | `.env.dev`(로컬) / `trade.env`(운영) → `BINNAIR_*` 환경변수 기반 EngineConfig |
| **domain** | Signal, Order, Position, Trade, Prediction, MarketSnapshot 등 엔진 내부 사용 객체 |
| **engine** | TradingEngine: process_tick(시세→진입/청산), 포지션 우선 분기, DB/거래소 복구·동기화 |
| **exchange** | ExchangeAdapter. 운영 기본은 BinanceFuturesAdapter, 그 외 Spot/Paper |
| **infra** | DB 모델, DTO, Repository. Postgres 연결 및 13개 테이블 CRUD |
| **market_data** | MarketDataProvider, PriceHistoryProvider. close 시계열(TimesFM 입력)과 OHLC(autopilot ATR 입력) 둘 다 제공 |
| **predictor** | Predictor. 운영 기본은 TimesFM, Dummy/RuleBased는 검증용 |
| **position** | PositionManager: open/close, 미실현 PnL, DB 스냅샷 복구 |
| **risk** | RiskChecker: 일손실/포지션한도/중복주문 검사 + 연속 손절 서킷브레이커. sizing: 잔고·손절거리 기반 수량 계산 |
| **signal** | 모델 BUY/HOLD/SELL을 연속 N회 확인 후 주문 가능 신호로 필터링 (진입·청산 각각) |
| **storage** | Order/Signal/Position/Trade/Audit 저장. PostgresDbStorage (backend=postgres) |
| **state** | StateManager: start/stop/heartbeat, JSON 파일 persist |
| **strategy** | Strategy.decide → OrderIntent. ExitManager: TP/SL 도달 여부 판단 (가격 기반 청산은 항상 최우선) |
| **api** | FastAPI read-only REST + WebSocket. 엔진 제어(start/stop/주문) 없음 — 조회 전용 |

---

## 설정

로컬은 프로젝트 루트 `.env.dev` (`BINNAIR_ENV=dev`), 서버는 `binnair-stack/env/trade.env` (`BINNAIR_ENV=prod`). 둘 다 gitignore 대상이며 이 리포에는 값이 커밋되지 않는다.

```bash
# 로컬 API
BINNAIR_API_HOST=127.0.0.1
BINNAIR_API_PORT=8000

# 서버 (compose.trading.yml)
BINNAIR_STORAGE_HOST=postgres
BINNAIR_API_HOST=0.0.0.0
BINNAIR_API_PORT=8001
BINNAIR_STATE_PERSIST_PATH=/data/state/engine_state.json
HF_HOME=/data/huggingface
```

### 진입/청산 핵심 설정

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `BINNAIR_TIMESFM_SIGNAL_THRESHOLD` | (미지정 시 자동계산) | 지정 시 `fee_rate*2+slippage_rate+safety_margin` 공식 대신 고정값 사용. **비워두는 것을 권장** — 원가 이하로 낮추면 노이즈 수준 신호로 과매매하게 됨 |
| `BINNAIR_TIMESFM_TIMEFRAME_THRESHOLD_SCALE` | true | timeframe 변경 시 entry threshold 자동 스케일 ([TIMESFM.md](./docs/TIMESFM.md)) |
| `BINNAIR_TIMESFM_PREDICT_ON_CANDLE_CLOSE` | true | 새 OHLCV 캔들 close 시에만 inference |
| `BINNAIR_TIMESFM_FORECAST_MODE` | average | `average`(권장) \| `last` |
| `BINNAIR_MARKET_ALIGN_POLL_WITH_TIMEFRAME` | true | poll interval을 timeframe 이상으로 자동 상향 |
| `BINNAIR_AUTOPILOT_SCORE_PERCENTILE` | 70 | 최근 |score| 분포에서 이 percentile 이상만 진입 허용 (adaptive threshold) |
| `BINNAIR_AUTOPILOT_BASE_CONSECUTIVE_REQUIRED` | 2 | 진입/청산 신호 확인 최소 연속 횟수. 1은 확인 없이 즉시 반응하므로 비권장 |
| `BINNAIR_AUTOPILOT_BASE_TP_ATR_MULT` / `_SL_ATR_MULT` | 2.0 / 1.2 | ATR 배수 기반 TP/SL. 내부적으로 수수료+슬리피지 원가 이하로는 좁혀지지 않도록 하한이 걸려 있음 |
| `BINNAIR_RISK_MIN_HOLD_SECONDS_BEFORE_SIGNAL_EXIT` | 90 | 진입 후 이 시간 전에는 모델 SELL 신호만으로 청산 안 함 (TP/SL은 예외 없이 즉시) |
| `BINNAIR_RISK_MAX_CONSECUTIVE_LOSSES` | 3 | 연속 손절 이 횟수 도달 시 신규 진입 차단 |
| `BINNAIR_RISK_CONSECUTIVE_LOSS_PAUSE_MINUTES` | 30 | 위 차단 지속 시간(분) |
| `BINNAIR_EXCHANGE_OCO_ENABLED` | false | 거래소 네이티브 TP/SL 보호주문 사용 여부. 기본은 로컬 폴링 기반 청산 |

---

## 실행

### DB 초기화 (Postgres 사용 시)

```bash
# 테이블 생성 (기존 스키마 보존)
python scripts/init_db.py

# 기존 테이블 삭제 후 재생성
python scripts/init_db.py --drop
```

### 자동매매 실행 (OHLCV 적재 + 엔진)

```bash
.venv/bin/python scripts/run_engine.py
```

### 조회 API 서버

```bash
.venv/bin/python scripts/run_api.py
# Swagger UI: http://127.0.0.1:8000/docs
```

### OHLCV 캔들 적재 (TimesFM 입력 히스토리)

```bash
# 최근 1분봉 500개를 DB ohlcv_candle에 upsert
.venv/bin/python scripts/ingest_ohlcv.py --symbol XRPUSDT --timeframe 1m --limit 500

# 계속 적재 (스케줄러/상시 프로세스용)
.venv/bin/python scripts/ingest_ohlcv.py --symbol XRPUSDT --timeframe 1m --limit 30 --loop --poll-interval 60
```

TimesFM 사용 시 권장 흐름:

```text
Binance klines → ohlcv_candle upsert → PriceHistoryProvider → TimesFMPredictor (close)
                                                             → RegimeDetector (high/low/close, True Range ATR)
```

`TimesFMPredictor`는 DB를 직접 알지 않고 `PriceHistoryProvider.get_recent_prices()`로 최근 close 시계열을 받는다.
`autopilot.RegimeDetector`는 같은 provider의 `get_recent_ohlc()`로 (high, low, close) 바를 받아 True Range 기반 ATR을 계산한다.
DB 히스토리가 `min_context`보다 부족하면 엔진 tick으로 쌓은 in-memory 가격 히스토리로 fallback한다.

**TimesFM 상세 (threshold·5m·hold_reason):** [docs/TIMESFM.md](./docs/TIMESFM.md)

### CLI (설치 후)

```bash
pip install -e .
binnair-engine
binnair-api
```

### 진입/청산 신호 정책

TimesFM의 단일 예측값은 바로 주문으로 쓰지 않고, `ConsecutiveSignalPolicy`가 심볼별 최근 시그널을 누적해 노이즈를 줄인다. 필요 연속 횟수는 Autopilot이 레짐(고변동성/횡보 등)에 따라 tick마다 조정한다.

```text
long_only (기본):
  포지션 없음 + BUY N회 연속        → 롱 진입
  포지션 없음 + SELL               → 대기 (롱 청산 신호만, 진입 아님)
  롱 보유 + SELL N회 연속          → 모델 청산 (MODEL_SELL)

long_short (선물 ONE_WAY 권장, BINNAIR_SIGNAL_MODE=long_short):
  포지션 없음 + BUY N회 연속        → 롱 진입
  포지션 없음 + SELL N회 연속       → 숏 진입
  롱 보유 + SELL N회 연속          → MODEL_SELL
  숏 보유 + BUY N회 연속           → MODEL_BUY

공통:
  매 tick TP/SL 도달 시 즉시 청산 (가격 조건 최우선)
  모델 청산은 min_hold_seconds_before_signal_exit 경과 후에만
```

### 지갑 잔고 기반 수량 계산

주문 수량은 고정 수량이 아니라 거래소 지갑의 `USDT availableBalance`를 기준으로 계산한다.

```text
허용 손실 = 지갑 잔고 * risk_per_trade_pct
손절 거리 = abs(진입가 - 손절가) / 진입가
이론 주문금액 = 허용 손실 / 손절 거리
최대 주문금액 = 지갑 잔고 * max_position_notional_pct
레버리지 상한 = 지갑 잔고 * max_leverage
최종 주문금액 = min(이론 주문금액, 최대 주문금액, 레버리지 상한)
quantity = 최종 주문금액 / 진입가
```

예를 들어 지갑이 100 USDT, `risk_per_trade_pct=0.005`, `sl_pct=0.005`, `max_position_notional_pct=0.20`이면 이론 주문금액은 100 USDT지만 최대 주문금액 제한 때문에 최종 주문금액은 20 USDT가 된다.

> 손절 거리(`sl_pct`)가 비정상적으로 좁으면 이론 주문금액이 과도하게 커질 수 있어, `autopilot.RegimeDetector.tp_sl_pct()`가 수수료+슬리피지 원가 이하로는 SL/TP가 좁혀지지 않도록 하한을 강제한다.

---

## position_snapshot / trade_result 청산 정보

CLOSED 행에는 다음 컬럼이 저장됨:

| 컬럼 | 설명 | 예 |
|------|------|-----|
| exit_reason | `TAKE_PROFIT` \| `STOP_LOSS` \| `MODEL_SELL` \| `EXCHANGE_SYNC` | TAKE_PROFIT |
| exit_price | 청산 가격 | 51001.0 |
| realized_pnl | 실현 손익 | +1001 (LONG TP) / -501 (LONG SL) |
| hold_seconds | 보유 시간(초) | 182 |

`EXCHANGE_SYNC`는 로컬 엔진이 모르는 사이 거래소 포지션이 사라졌을 때(수동 청산, 청산 등) 기록되며, 이 경우도 마지막 가격을 TP/SL 가격과 비교해 가능하면 `TAKE_PROFIT`/`STOP_LOSS`로 best-effort 추정한다.

---

## BinnAIR 추적 필드

- `version`, `run_id`, `strategy_id`, `model_version`, `feature_set_version`
- config.run_context 및 EngineContext에 포함

---

## 기술 스택

- Python 3.12
- FastAPI, uvicorn (조회 API)
- SQLAlchemy 2.x, psycopg (Postgres)
- httpx (Binance REST), websockets (User Data Stream)
- torch, timesfm (예측 모델)
- pytest (테스트)

---

## 실거래 (Binance Futures)

`.env.dev` 또는 `trade.env`에서 `BINNAIR_EXCHANGE_PAPER_MODE=false`, `BINNAIR_EXCHANGE_API_KEY`, `BINNAIR_EXCHANGE_API_SECRET`, `BINNAIR_EXCHANGE_BASE_URL` 설정.

- 테스트넷: `BINNAIR_EXCHANGE_BASE_URL=https://testnet.binancefuture.com`
- 메인넷: `BINNAIR_EXCHANGE_BASE_URL=https://fapi.binance.com`

> `paper_mode=false`여도 `base_url`이 테스트넷이면 실거래가 아니라 테스트넷 자금으로 동작한다. 운영 전환 전 반드시 `base_url`과 API 키가 메인넷 것인지 확인할 것.

---

## 관련 문서

- [docs/PERSISTENCE.md](docs/PERSISTENCE.md) - DB 테이블, DTO, Repository 상세
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - REST/WebSocket API 전체 레퍼런스
