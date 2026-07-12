# Persistence 계층

자동매매 엔진 실행 이력 저장 구조. 스키마: PostgreSQL `trade` (schema, `infra/persistence/models.py:SCHEMA`).

## 개요

- **DTO**: Repository 입출력용. Domain model과 분리. 조회용 `*DTO`, 저장 입력용 `*Create` 두 종류가 있다.
- **DB Model**: SQLAlchemy 2.x 모델 (`infra/persistence/models.py`). 테이블 스키마.
- **Repository**: 인터페이스(`repositories/interfaces.py`) + Postgres 구현(`repositories/postgres.py`). DTO ↔ DB 변환 담당.

## 테이블 목록 (15개)

| 테이블 | 역할 |
|--------|------|
| **ohlcv_candle** | Binance 등 거래소 OHLCV 원천 캔들. TimesFM 입력 close 히스토리 + autopilot True Range ATR(high/low) 입력 |
| **engine_run** | 엔진 실행 단위. `status`: `running`(매매중) \| `paused`(UI 매매중지) \| `stopped`(프로세스종료) \| `error` |
| **engine_runtime_state** | **UI L1 런타임 설정** + `trading_enabled` (매매 on/off). user_id당 1 row |
| **engine_command** | UI start/stop 명령 큐. 엔진이 poll 후 `pending`→`done`/`failed` |
| **strategy_config_snapshot** | 실행 시점 전략 설정 스냅샷. replay/debug용 |
| **signal_event** | Predictor/Strategy 출력 시그널 (BUY/SELL/HOLD). symbol, model_version, timeframe |
| **order_request** | 엔진 → 거래소 전달 직전 주문 요청 |
| **order_execution** | 주문 체결 결과. raw_response에 거래소 응답 원문. order_request FK |
| **position_snapshot** | 특정 시점 포지션 스냅샷 (OPEN/CLOSED). TP/SL, exit_reason, realized_pnl 포함 |
| **trade_result** | **청산 완료 거래 1건 = 1 row.** 승률·PnL 집계의 원천 데이터 (`position_snapshot`과 별개로 정규화된 요약) |
| **performance_daily** | run_id + UTC 일자별 성과 롤업. `trade_result` 청산 시 upsert. 승률·수익률 API의 일 단위 소스 |
| **equity_snapshot** | 잔고 스냅샷 (엔진 시작 시 / 청산 시). 기간 수익률(%) 계산의 분모(기준 자본) |
| **risk_event** | 리스크 거부/경고 이벤트 (`event_type`, `reason`, `intent_data`) |
| **model_inference_event** | 모델 추론 I/O (`input_snapshot`, `output_prediction`). 엔진은 매 inference tick 저장. `output_prediction.hold_reason`으로 HOLD 원인 구분 ([TIMESFM.md](./TIMESFM.md)) |
| **audit_log** | 모든 주요 이벤트 최종 기록 (`risk_rejected`, `position_closed` 등) |

> `position_snapshot`과 `trade_result`의 차이: `position_snapshot`은 OPEN/CLOSED 모든 상태 변화를 남기는 원시 이력이고, `trade_result`는 CLOSED 시점에 진입→청산 1라운드를 요약해 별도로 만드는 집계 전용 테이블이다 (`performance/metrics.py:build_trade_result_create`).

## exit_reason 값

`position_snapshot.exit_reason`, `trade_result.exit_reason`에 저장되는 값:

| 값 | 의미 |
|----|------|
| `TAKE_PROFIT` | 가격이 TP 도달 (`strategy/exit_manager.py`) |
| `STOP_LOSS` | 가격이 SL 도달 |
| `MODEL_SELL` | 모델 SELL 신호 연속 N회 (롱 청산, 최소 보유시간 경과 후) |
| `MODEL_BUY` | 모델 BUY 신호 연속 N회 (숏 청산, `long_short` 모드) |
| `SHUTDOWN` | graceful 종료 시 강제 청산 |
| `EXCHANGE_SYNC` | 로컬 모르게 거래소 포지션이 사라짐 (수동 청산 등). 가능하면 TP/SL 가격과 비교해 `TAKE_PROFIT`/`STOP_LOSS`로 best-effort 재추정 후 기록, 판단 불가 시 `EXCHANGE_SYNC` 유지 |

## DTO 목록 (`infra/persistence/dto.py`)

조회용(`*DTO`, `id`/`created_at` 포함)과 저장 입력용(`*Create`, PK 없음) 쌍으로 존재한다.

| 테이블 | 조회 DTO | 생성 DTO |
|--------|----------|----------|
| engine_run | `EngineRunDTO` | `EngineRunCreate` |
| engine_runtime_state | `EngineRuntimeStateDTO` | `EngineRuntimeStateUpsert` |
| engine_command | `EngineCommandDTO` | `EngineCommandCreate` |
| strategy_config_snapshot | `StrategyConfigSnapshotDTO` | `StrategyConfigSnapshotCreate` |
| signal_event | `SignalEventDTO` | `SignalEventCreate` |
| order_request | `OrderRequestDTO` | `OrderRequestCreate` |
| order_execution | `OrderExecutionDTO` | `OrderExecutionCreate` |
| position_snapshot | `PositionSnapshotDTO` | `PositionSnapshotCreate` |
| trade_result | `TradeResultDTO` | `TradeResultCreate` |
| performance_daily | `PerformanceDailyDTO` | (upsert 시 직접 구성) |
| equity_snapshot | `EquitySnapshotDTO` | `EquitySnapshotCreate` |
| risk_event | — | `RiskEventCreate` |
| model_inference_event | — | `ModelInferenceEventCreate` |
| audit_log | — | `AuditLogCreate` |
| ohlcv_candle | — | `OhlcvCandleCreate` (batch upsert) |

## 사용자별 이력 분리 (user_id)

모든 이력/주문 테이블에 `user_id VARCHAR(36)` 컬럼 존재. 사용자별 이력 조회·관리용.

- config `run_context.user_id` (기본값 `"default"`)
- Web 로그인 시 사용자 UUID 전달 예정

## OHLCV 캔들 저장

`ohlcv_candle`은 외부 거래소에서 받은 캔들 원천 데이터를 저장한다.

- 고유키: `symbol`, `timeframe`, `open_time`
- 적재 방식: `INSERT ... ON CONFLICT DO UPDATE` (`OhlcvCandlePostgresRepository.upsert_many`)
- 조회 메서드 2종:
  - `get_recent_closes(symbol, timeframe, limit)` → `list[float]` — TimesFM 입력용 close 시계열
  - `get_recent_ohlc(symbol, timeframe, limit)` → `list[tuple[high, low, close]]` — autopilot `RegimeDetector`의 True Range ATR 계산용 (종가 차분만으로는 캔들 내 변동폭을 놓치기 때문에 고가/저가를 별도로 제공)
- 보조 사용처: 백테스트, 리플레이, 신호 디버깅

같은 캔들을 반복 적재해도 중복 row는 생기지 않는다. 상시 적재는 최근 N개 캔들을 반복 조회해 작은 공백을 upsert로 메우는 방식이 권장된다.

## 추적 필드 (replay/debug)

- `user_id`, `run_id`, `strategy_id`, `symbol`, `timeframe`, `model_version`, `feature_set_version`
- `timestamp`/`event_at`/`snapshot_at`/`executed_at`/`opened_at`/`closed_at`
- `paper_mode`: paper/live 구분
- `correlation_id`: 같은 tick에서 발생한 이벤트(추론→시그널→주문→포지션) 연관 추적

## init_db 사용법

```bash
# 테이블 생성 (기존 스키마 보존)
python scripts/init_db.py

# 기존 테이블 삭제 후 재생성
python scripts/init_db.py --drop
```

## UI 런타임 설정 (L0 + L1)

| 계층 | 저장소 | 내용 |
|------|--------|------|
| **L0** | `trade.env` | API 키, DB 접속, HF 모델 경로, API host/port 등 비밀·인프라 |
| **L1** | `engine_runtime_state.config_json` | symbol, signal_mode, TP/SL, TimesFM, Autopilot 등 UI 파라미터 |

흐름: UI → `PUT/POST /api/v1/control/*` → DB 저장 → 엔진 `RuntimeControlPoller`가 명령 poll → `merge_runtime_config(env, L1)` → tick 실행.

- **프로세스 기동 직후:** `trading_enabled=false`, `engine_run.status=paused` (UI Start 전까지 매매 없음)
- `trading_enabled=false` (UI Stop): 신규 진입만 중단. `engine_run.status=paused`. 보유 포지션 TP/SL·청산은 계속
- `trading_enabled=true` (UI Start): `engine_run.status=running`
- `engine_run.status=stopped`: 엔진 **프로세스** 종료 시에만 (UI Stop과 다름)
- `engine_command`: `start` / `stop` (status: `pending` → `done` / `failed`)

스키마 정의: `config/runtime_config.py` (`RuntimeConfigParams`, `RUNTIME_PARAM_SCHEMA`).

## 환경변수

DB 연결은 단일 `DATABASE_URL`이 아니라 `BINNAIR_STORAGE_*` 값을 조합해 만든다 (`config/settings.py:StorageConfig.to_database_url()`).

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `BINNAIR_STORAGE_BACKEND` | `postgres` | `memory` \| `postgres` |
| `BINNAIR_STORAGE_HOST` | `localhost` | |
| `BINNAIR_STORAGE_PORT` | `5432` | |
| `BINNAIR_STORAGE_DBNAME` | `binnair` | |
| `BINNAIR_STORAGE_USER` | `binnair` | |
| `BINNAIR_STORAGE_PASSWORD` | — | |
| `BINNAIR_STORAGE_SCHEMA` | `trade` | |

내부적으로 `postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}` 형태로 조립되어 psycopg3 드라이버로 연결한다.

## Migration 가이드 (Alembic)

향후 Alembic 도입 시:

```bash
# 설치
pip install alembic

# 초기화
alembic init alembic

# env.py 에서 Base, target_metadata 설정
# alembic/versions/ 에 마이그레이션 스크립트 생성

# 마이그레이션 적용
alembic upgrade head
```

현재는 `init_db.py`로 스키마 생성. 프로덕션에서는 Alembic 사용 권장.
