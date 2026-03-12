# BinnAIR Automated Trading Engine

자동매매 실행 엔진. Paper trading 기본, 확장 가능한 엔진 중심 구조.

## Quick Start (환경 구성)

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

# 3. 의존성 설치 (Poetry 또는 uv 사용 시 venv 자동 생성)
poetry install
# 또는
uv sync
```

**Poetry/uv**: `.venv` 자동 생성 → 1~2단계 생략 가능.

**pip만 사용할 경우**:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -e .
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

## 확장 예정

- 실거래 Binance 어댑터
- 실제 PostgreSQL 연결
- TorchPredictor 실제 추론
- 시그널 소스(폴링/웹소켓) 연동
