# Persistence 계층

자동매매 엔진 실행 이력 저장 구조.

## 개요

- **DTO**: Repository 입출력용. Domain model과 분리.
- **DB Model**: SQLAlchemy 2.x 모델. 테이블 스키마.
- **Repository**: 인터페이스 + Postgres 구현. DTO ↔ DB 변환 담당.

## 테이블/엔티티 역할

| 테이블 | 역할 |
|--------|------|
| **ohlcv_candle** | Binance 등 거래소 OHLCV 원천 캔들. TimesFM 입력 close 히스토리와 백테스트/리플레이 기반 |
| **engine_run** | 엔진 실행 단위 (BinnAIR pipeline_runs 유사). run_id, strategy_id, model_version, paper_mode, status, started_at/stopped_at |
| **strategy_config_snapshot** | 실행 시점 전략 설정 스냅샷. replay/debug용 |
| **signal_event** | Predictor/Strategy 출력 시그널 (BUY/SELL/HOLD). symbol, model_version, timeframe |
| **order_request** | 엔진 → 거래소 전달 직전 주문 요청 |
| **order_execution** | 주문 체결 결과. raw_response에 거래소 응답 원문 |
| **position_snapshot** | 특정 시점 포지션 스냅샷 |
| **risk_event** | 리스크 거부/경고 이벤트 |
| **model_inference_event** | 모델 추론 I/O (input_snapshot, output_prediction). **BUY/SELL 시에만 저장**, HOLD 틱은 저장 안 함 |
| **audit_log** | 모든 주요 이벤트 최종 기록 |

## 사용자별 이력 분리 (user_id)

모든 이력/주문 테이블에 `user_id VARCHAR(36)` 컬럼 존재. 사용자별 이력 조회·관리용.

- config `run_context.user_id` (기본값 `"default"`)
- Web 로그인 시 사용자 UUID 전달 예정

## OHLCV 캔들 저장

`ohlcv_candle`은 외부 거래소에서 받은 캔들 원천 데이터를 저장한다.

- 고유키: `symbol`, `timeframe`, `open_time`
- 적재 방식: `INSERT ... ON CONFLICT DO UPDATE`
- 기본 사용처: TimesFM 입력용 최근 `close` 시계열
- 보조 사용처: 백테스트, 리플레이, 신호 디버깅

같은 캔들을 반복 적재해도 중복 row는 생기지 않는다. 상시 적재는 최근 N개 캔들을 반복 조회해 작은 공백을 upsert로 메우는 방식이 권장된다.

## 추적 필드 (replay/debug)

- `user_id`, `run_id`, `strategy_id`, `symbol`, `timeframe`, `model_version`, `feature_set_version`
- `timestamp`/`event_at`/`snapshot_at`/`executed_at`
- `paper_mode`: paper/live 구분
- `correlation_id`: 이벤트 연관 추적

## init_db 사용법

```bash
# 테이블 생성
python scripts/init_db.py

# 기존 테이블 삭제 후 재생성
python scripts/init_db.py --drop
```

## 환경변수

- `DATABASE_URL`: Postgres 연결 문자열  
  예: `postgresql://user:pass@localhost:5432/binnair_engine`

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
