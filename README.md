# BinnAIR Automated Trading Engine

자동매매 실행 엔진. Paper trading 기본, 확장 가능한 엔진 중심 구조.

## Quick Start (환경 구성)

**의존성 한 줄 설치** (가상환경 활성화 후 프로젝트 루트에서):

```bash
pip install -e .
```

위 명령으로 `pyproject.toml`에 정의된 모든 의존성(sqlalchemy, pyyaml, torch, psycopg, httpx, aiohttp 등)이 설치됩니다.

---

전체 절차:

```bash
# 1. venv 생성 (Python 3.12)
python -m venv .venv

# 2. venv 활성화
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# Linux/macOS
source .venv/bin/activate

# 3. 의존성 설치
pip install -e .
```

**Poetry/uv 사용 시** (venv 자동 생성):
```bash
poetry install
# 또는
uv sync
```

## 디렉터리 구조

```
src/binnair_trading_engine/
├── app/                 # 부트스트랩 및 진입점
│   ├── bootstrap.py     # 설정 로드, DI, 엔진 인스턴스 생성
│   └── main.py           # CLI 진입점
├── config/              # 설정
│   └── settings.py      # EngineConfig, load_config (YAML/환경변수)
├── domain/              # 도메인 모델
│   └── models.py        # Signal, Order, OrderIntent, Position, Trade, TradeContext, Prediction, AuditLog
├── engine/              # 엔진 코어
│   └── core.py          # TradingEngine, process_signal 파이프라인
├── market_data/         # 시세 수신
│   ├── interface.py     # MarketDataProvider
│   └── binance_rest.py  # Binance REST ticker/price 폴링
├── exchange/            # 거래소 어댑터
│   ├── interface.py     # ExchangeAdapter (Binance 기준 설계)
│   └── paper.py         # PaperExchangeAdapter (종이거래)
├── predictor/           # 추론/모델 (인터페이스 분리)
│   ├── interface.py     # Predictor
│   ├── dummy.py         # DummyPredictor (HOLD 기본)
│   └── torch_predictor.py  # TorchPredictor 플레이스홀더
├── risk/                # 리스크 관리
│   ├── checker.py       # RiskChecker
│   └── default.py       # DefaultRiskChecker
├── storage/             # 저장 레이어
│   ├── interface.py     # OrderStore, SignalStore, PositionStore, TradeStore, AuditStore, StorageLayer
│   └── postgres.py      # PostgresStorage (초기 메모리)
├── state/               # 상태 관리 (장애 복구)
│   └── manager.py       # StateManager (메모리 + 파일 persist)
├── strategy/            # 전략
│   ├── interface.py     # Strategy
│   └── passthrough.py   # PassthroughStrategy
├── api/                 # (옵션) 최소 API
scripts/
├── run_engine.py         # 엔진 실행 스크립트
config/
├── config.example.yaml  # 설정 예시
tests/
```

## 모듈 역할

| 모듈 | 역할 |
|------|------|
| **app** | bootstrap: 설정 로드 → 의존성 생성 → TradingEngine 반환. main: CLI 진입점 |
| **config** | YAML/환경변수 기반 EngineConfig. run_context, exchange, storage, predictor_type 등 |
| **domain** | Signal, Order, OrderIntent, Position, Trade, TradeContext, Prediction, AuditLog, EngineContext |
| **engine** | TradingEngine: process_signal(시그널→저장→예측→전략→리스크→주문→상태), run_cycle |
| **exchange** | ExchangeAdapter 인터페이스. PaperExchangeAdapter로 paper trading |
| **predictor** | Predictor 인터페이스. DummyPredictor, TorchPredictor(플레이스홀더) |
| **risk** | RiskChecker: check(intent, ctx) → bool. DefaultRiskChecker |
| **storage** | Order/Signal/Position/Trade/Audit 별 Store. StorageLayer 통합. PostgresStorage(메모리) |
| **state** | StateManager: start/stop/heartbeat/update_position. JSON 파일 persist |
| **strategy** | Strategy: decide(signal, pred, ctx) → OrderIntent. PassthroughStrategy |

## BinnAIR 추적 필드

- `version`, `run_id`, `strategy_id`, `model_version`, `feature_set_version`

config.run_context 및 EngineContext에 포함.

## 실행

```bash
# 개발 시
python scripts/run_engine.py -c config/config.example.yaml

# 설치 후
pip install -e .
binnair-engine -c config/config.example.yaml
```

## 설정 (config.example.yaml)

```yaml
run_context:
  run_id: "run_001"
  strategy_id: "strategy_default"
  model_version: "v1"
  feature_set_version: "v1"
  version: "1.0.0"

market_data:
  enabled: false   # true 시 Binance REST로 시세 폴링 → engine.run_cycle(snapshot)
  symbol: "BTCUSDT"
  poll_interval_seconds: 5.0

exchange:
  paper_mode: true   # 기본값

predictor_type: "dummy"
risk_enabled: true
state_persist_path: "./data/state"
```

## 의존성 관리 (Poetry / uv)

```bash
# Poetry
poetry install
poetry run binnair-engine -c config/config.example.yaml

# uv
uv sync
uv run binnair-engine -c config/config.example.yaml
```

## 기술 스택

- Python 3.12
- pydantic v2 / pydantic-settings
- SQLAlchemy 2.x, psycopg
- httpx, aiohttp, websockets
- torch
- redis (optional)
- structlog (로깅)
- pytest (테스트)

## 실거래 (Binance Spot)

`config.yaml`에서 `exchange.paper_mode: false`로 설정하고 `api_key`, `api_secret` 입력 시 Binance Spot 실거래 연동.

- `BinanceSpotAdapter`: place_order, cancel_order, get_position, get_order 등 REST API 호출
- 테스트넷: `base_url: "https://testnet.binance.vision"`

## 확장 예정
- TorchPredictor 실제 추론
- 시세 WebSocket 구독 (현재 REST 폴링만 지원)
