# BinnAIR Automated Trading Engine

자동매매 실행 엔진. Paper trading 기본, 확장 가능한 엔진 중심 구조.

---

## 구현 현황 (Implementation Status)

### ✅ 완료된 기능

| 영역 | 구현 내용 | 비고 |
|------|-----------|------|
| **진입** | Predictor → Signal → Strategy → Risk → Exchange 주문 | BUY 시 TP/SL 계산, position_snapshot 저장 |
| **보유** | 포지션 유지, 주문 없음 | TP/SL 범위 내 가격이면 hold |
| **청산** | ExitManager TP/SL 도달 시 SELL | TAKE_PROFIT / STOP_LOSS 구분 저장 |
| **재기동** | DB `position_snapshot`에서 OPEN 포지션 복구 | `get_latest_open_position_snapshots` |
| **Persistence** | engine_run, signal_event, order_request, order_execution, position_snapshot, model_inference_event, audit_log | PostgreSQL + init_db migration |
| **청산 결과** | position_snapshot에 exit_reason, exit_price, realized_pnl | CLOSED 행에서 결과 평가 가능 |

### 🔶 부분 구현

| 영역 | 구현 내용 | 미구현 |
|------|-----------|--------|
| **Predictor** | TimesFM, Dummy, RuleBased | TimesFM은 DB OHLCV close 히스토리 기반 zero-shot 예측 |
| **Market Data** | Binance REST ticker/price 폴링 | WebSocket 구독 없음 |
| **Exchange** | Paper, Binance Spot REST | Futures, WebSocket 주문 없음 |
| **Storage** | memory / postgres 백엔드 | Redis, Alembic migration 없음 |

### ❌ 미구현

- Trailing stop, partial exit (부분 청산)
- Predictor 반대 신호 기반 청산 (TP/SL만 지원)
- 일별 PnL 집계 API / 대시보드
- Web API (REST/gRPC)
- Redis 캐시
- Alembic 마이그레이션 (현재 init_db.py로 ADD COLUMN IF NOT EXISTS)

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
├── config/                 # 설정
│   ├── settings.py        # EngineConfig, load_config
│   └── env_loader.py      # BINNAIR_* 환경변수 → EngineConfig
├── domain/                 # 도메인 모델 (엔진 내부 사용 객체)
│   └── models.py          # Signal, Order, Position, Trade, Prediction, MarketSnapshot 등
├── engine/                 # 엔진 코어
│   └── core.py            # TradingEngine: 진입/청산 흐름, process_tick, run_cycle
├── exchange/               # 거래소 어댑터
│   ├── interface.py       # ExchangeAdapter
│   ├── paper.py           # PaperExchangeAdapter (종이거래)
│   └── binance_spot.py    # BinanceSpotAdapter (실거래 REST)
├── infra/                  # DB/Persistence 인프라
│   └── persistence/
│       ├── session.py     # DB Engine/Session
│       ├── models.py     # SQLAlchemy ORM (테이블 정의)
│       ├── dto.py        # Repository 입출력 DTO (*Create)
│       └── repositories/
│           ├── interfaces.py  # Repository Protocol
│           └── postgres.py    # Postgres 구현체
├── market_data/            # 시세 수신
│   ├── interface.py       # MarketDataProvider
│   ├── history.py         # PriceHistoryProvider, OHLCV DB close 히스토리 공급
│   └── binance_rest.py    # Binance REST ticker/price 및 klines 조회
├── predictor/              # 추론/모델
│   ├── interface.py       # Predictor
│   ├── dummy.py           # DummyPredictor (테스트용)
│   ├── rule_based.py      # RuleBasedPredictor (가격 규칙)
│   └── timesfm_predictor.py # TimesFM 기반 zero-shot 예측
├── position/               # 포지션 관리
│   └── manager.py         # PositionManager: open/close, restore_from_snapshot
├── risk/                   # 리스크 관리
│   ├── checker.py         # RiskChecker
│   └── default.py         # DefaultRiskChecker
├── signal/                 # 모델 시그널 후처리 정책
│   └── policy.py          # ConsecutiveSignalPolicy
├── storage/                # 저장 레이어
│   ├── interface.py       # OrderStore, SignalStore, PositionStore 등
│   ├── postgres.py        # PostgresStorage (메모리, backend=memory)
│   └── postgres_db.py     # PostgresDbStorage (실제 DB, backend=postgres)
├── state/                  # 상태 관리 (장애 복구)
│   └── manager.py         # StateManager
├── strategy/               # 전략 및 청산
│   ├── interface.py       # Strategy
│   ├── passthrough.py     # PassthroughStrategy
│   └── exit_manager.py    # ExitManager (TP/SL 판단)
└── api/                    # (옵션) 최소 API

scripts/
├── init_db.py                    # DB 테이블 생성 및 position_snapshot migration
├── ingest_ohlcv.py               # Binance OHLCV 캔들 적재 (TimesFM 입력 히스토리)
├── run_engine.py                 # OHLCV 적재 + 매매 엔진 한 번에 실행
├── run_api.py                    # 조회 API 서버
└── download_timesfm_weights.py   # TimesFM 가중치 다운로드

.env.dev                 # 로컬 개발 설정 (gitignore, BINNAIR_*)
compose.trading.yml      # binnair-stack compose.yml에 붙여 넣을 서비스 스니펫
Dockerfile.engine / Dockerfile.api
bin/                     # 서버 재기동·DB 초기화 스크립트
```

---

## 모듈 역할

| 모듈 | 역할 |
|------|------|
| **app** | bootstrap: 설정 로드 → DI → TradingEngine. main: CLI 진입점 |
| **config** | `.env.dev` / `BINNAIR_*` 환경변수 기반 EngineConfig |
| **domain** | Signal, Order, Position, Trade, Prediction, MarketSnapshot 등 엔진 내부 사용 객체 |
| **engine** | TradingEngine: process_tick(시세→진입/청산), 포지션 우선 분기, DB 복구 |
| **exchange** | ExchangeAdapter. PaperExchangeAdapter / BinanceSpotAdapter |
| **infra** | DB 모델, DTO, Repository. Postgres 연결 및 OHLCV/position_snapshot 등 테이블 CRUD |
| **market_data** | MarketDataProvider, PriceHistoryProvider. Binance REST 시세/OHLCV 조회 |
| **predictor** | Predictor. 운영 기본은 TimesFM, Dummy/RuleBased는 검증용 |
| **position** | PositionManager: open/close, 미실현 PnL, DB 스냅샷 복구 |
| **risk** | RiskChecker: check(intent, ctx) → passed/rejected |
| **signal** | TimesFM BUY/HOLD/SELL을 주문 가능한 정책 신호로 필터링 |
| **storage** | Order/Signal/Position/Trade/Audit 저장. PostgresDbStorage (backend=postgres) |
| **state** | StateManager: start/stop/heartbeat, JSON 파일 persist |
| **strategy** | Strategy.decide → OrderIntent. ExitManager: TP/SL 도달 여부 판단 |

---

## 설정

로컬은 프로젝트 루트 `.env.dev` ( `BINNAIR_ENV=dev` ), 서버는 `binnair-stack/env/trade.env` ( `BINNAIR_ENV=prod` ).

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

---

## 실행[PLAY]

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

### OHLCV 캔들 적재 (TimesFM 입력 히스토리)

```bash
# 최근 1분봉 500개를 DB ohlcv_candle에 upsert
.venv/bin/python scripts/ingest_ohlcv.py --symbol BTCUSDT --timeframe 1m --limit 500

# 계속 적재 (스케줄러/상시 프로세스용)
.venv/bin/python scripts/ingest_ohlcv.py --symbol BTCUSDT --timeframe 1m --limit 30 --loop --poll-interval 60
```

TimesFM 사용 시 권장 흐름:

```text
Binance klines → ohlcv_candle upsert → PriceHistoryProvider → TimesFMPredictor
```

`TimesFMPredictor`는 DB를 직접 알지 않고 `PriceHistoryProvider`로 최근 close 시계열을 받는다.
DB 히스토리가 `min_context`보다 부족하면 엔진 tick으로 쌓은 in-memory 가격 히스토리로 fallback한다.

### CLI (설치 후)

```bash
pip install -e .
binnair-engine
```

### TimesFM 3회 시그널 정책

TimesFM의 단일 예측값은 바로 주문으로 쓰지 않고, `ConsecutiveSignalPolicy`가 심볼별 최근 시그널을 누적해 노이즈를 줄인다.

```text
포지션 없음 + BUY 3회 연속  → 롱 진입
포지션 없음 + HOLD/SELL     → 대기
롱 포지션 있음 + SELL 3회 연속 → 시장가 청산
롱 포지션 있음 + BUY/HOLD   → 유지, TP/SL 계속 감시
```

`SELL`은 1차 정책에서 숏 진입이 아니라 **롱 청산 신호**로만 사용한다.

### 지갑 잔고 기반 수량 계산

주문 수량은 고정 수량이 아니라 Binance 테스트넷 지갑의 `USDT availableBalance`를 기준으로 계산한다.

```text
허용 손실 = 지갑 잔고 * risk_per_trade_pct
손절 거리 = abs(진입가 - 손절가) / 진입가
이론 주문금액 = 허용 손실 / 손절 거리
최대 주문금액 = 지갑 잔고 * max_position_notional_pct
최종 주문금액 = min(이론 주문금액, 최대 주문금액, 레버리지 상한)
quantity = 최종 주문금액 / 진입가
```

예를 들어 지갑이 100 USDT, `risk_per_trade_pct=0.005`, `sl_pct=0.005`, `max_position_notional_pct=0.20`이면 이론 주문금액은 100 USDT지만 최대 주문금액 제한 때문에 최종 주문금액은 20 USDT가 된다.

---

## position_snapshot 청산 정보

CLOSED 행에는 다음 컬럼이 저장됨:

| 컬럼 | 설명 | 예 |
|------|------|-----|
| exit_reason | TAKE_PROFIT \| STOP_LOSS | TAKE_PROFIT |
| exit_price | 청산 가격 | 51001.0 |
| realized_pnl | 실현 손익 | +1001 (LONG TP) / -501 (LONG SL) |

---

## BinnAIR 추적 필드

- `version`, `run_id`, `strategy_id`, `model_version`, `feature_set_version`
- config.run_context 및 EngineContext에 포함

---

## 기술 스택

- Python 3.12
- pydantic v2 / pydantic-settings
- SQLAlchemy 2.x, psycopg
- httpx, aiohttp
- torch
- redis (optional)
- structlog (로깅)
- pytest (테스트)

---

## 실거래 (Binance Futures)

`.env.dev` 또는 `trade.env`에서 `BINNAIR_EXCHANGE_PAPER_MODE=false`, `BINNAIR_EXCHANGE_API_KEY`, `BINNAIR_EXCHANGE_API_SECRET` 설정.

- 테스트넷: `BINNAIR_EXCHANGE_BASE_URL=https://testnet.binancefuture.com`

---

## 관련 문서

- [PERSISTENCE.md](PERSISTENCE.md) - DB 테이블, DTO, Repository 상세
