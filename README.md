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
| **Predictor** | Dummy, RuleBased, TorchPredictor | TorchPredictor: DummyFeatureVectorProvider만 연결 (실제 피처 공학 미구현) |
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
python -m venv .venv

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
│   └── settings.py        # EngineConfig, load_config (YAML/환경변수)
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
│   └── binance_rest.py    # Binance REST ticker/price 폴링
├── predictor/              # 추론/모델
│   ├── interface.py       # Predictor
│   ├── dummy.py           # DummyPredictor (테스트용)
│   ├── rule_based.py      # RuleBasedPredictor (가격 규칙)
│   ├── torch_predictor.py # TorchPredictor (PyTorch)
│   ├── artifact.py        # ModelArtifactMetadata
│   └── feature_provider.py # FeatureVectorProvider
├── position/               # 포지션 관리
│   └── manager.py         # PositionManager: open/close, restore_from_snapshot
├── risk/                   # 리스크 관리
│   ├── checker.py         # RiskChecker
│   └── default.py         # DefaultRiskChecker
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
├── init_db.py             # DB 테이블 생성 및 position_snapshot migration
└── verify_mvp.py          # MVP 검증 (진입→TP/SL 청산, DB 기록 검증)

config/
└── config.yaml            # 설정 (storage.backend=postgres 필요 시 직접 생성)
```

---

## 모듈 역할

| 모듈 | 역할 |
|------|------|
| **app** | bootstrap: 설정 로드 → DI → TradingEngine. main: CLI 진입점 |
| **config** | YAML/환경변수 기반 EngineConfig. run_context, exchange, storage, trade_rules, predictor_type 등 |
| **domain** | Signal, Order, Position, Trade, Prediction, MarketSnapshot 등 엔진 내부 사용 객체 |
| **engine** | TradingEngine: process_tick(시세→진입/청산), 포지션 우선 분기, DB 복구 |
| **exchange** | ExchangeAdapter. PaperExchangeAdapter / BinanceSpotAdapter |
| **infra** | DB 모델, DTO, Repository. Postgres 연결 및 position_snapshot 등 테이블 CRUD |
| **market_data** | MarketDataProvider. Binance REST 시세 폴링 |
| **predictor** | Predictor. DummyPredictor, RuleBasedPredictor, TorchPredictor |
| **position** | PositionManager: open/close, 미실현 PnL, DB 스냅샷 복구 |
| **risk** | RiskChecker: check(intent, ctx) → passed/rejected |
| **storage** | Order/Signal/Position/Trade/Audit 저장. PostgresDbStorage (backend=postgres) |
| **state** | StateManager: start/stop/heartbeat, JSON 파일 persist |
| **strategy** | Strategy.decide → OrderIntent. ExitManager: TP/SL 도달 여부 판단 |

---

## 실행

### DB 초기화 (Postgres 사용 시)

```bash
# 테이블 생성 (기존 스키마 보존)
python scripts/init_db.py

# 기존 테이블 삭제 후 재생성
python scripts/init_db.py --drop
```

### MVP 검증 (진입 → TP/SL 청산)

```bash
CONFIG_PATH=config/config.yaml python scripts/verify_mvp.py
```

### CLI (설치 후)

```bash
pip install -e .
binnair-engine -c config/config.yaml
```

---

## 설정 (config.yaml)

`config/config.yaml`이 없으면 `config/` 디렉터리를 만들고 아래 예시를 참고해 생성하세요.

```yaml
run_context:
  run_id: "run_001"
  strategy_id: "strategy_default"
  model_version: "v1"
  feature_set_version: "v1"
  version: "1.0.0"
  user_id: "default"   # 사용자별 이력 분리 (UUID 등, VARCHAR 36)

market_data:
  enabled: false   # true 시 Binance REST 시세 폴링
  symbol: "BTCUSDT"
  poll_interval_seconds: 5.0

exchange:
  market_type: "futures"   # "spot" | "futures"
  paper_mode: true
  leverage: 3
  margin_type: "ISOLATED"  # ISOLATED | CROSSED
  position_side_mode: "ONE_WAY"  # ONE_WAY | HEDGE
  oco_enabled: true

storage:
  backend: "postgres"   # "memory" | "postgres"
  host: "localhost"
  port: 5432
  dbname: "binnair_engine"
  user: "postgres"
  password: "***"
  schema: "trade"

trade_rules:
  tp_pct: 0.02   # TP: 체결가 * (1 + tp_pct)
  sl_pct: 0.01   # SL: 체결가 * (1 - sl_pct)

predictor_type: "dummy"   # "dummy" | "rule_based" | "torch"
risk_enabled: true
state_persist_path: "./data/state"
```

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

## 실거래 (Binance Spot)

`config.yaml`에서 `exchange.paper_mode: false`, `api_key`, `api_secret` 설정 시 Binance Spot 실거래.

- `BinanceSpotAdapter`: place_order, cancel_order, get_position, get_order 등 REST
- 테스트넷: `base_url: "https://testnet.binance.vision"`

---

## 관련 문서

- [PERSISTENCE.md](PERSISTENCE.md) - DB 테이블, DTO, Repository 상세
