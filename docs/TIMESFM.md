# TimesFM 예측·신호 로직

TimesFM(`google/timesfm-2.5-200m-pytorch`)을 BinnAIR 엔진에 연결하는 방식, 2026-07 개선 내용, 운영 튜닝 가이드.

---

## 1. 데이터 흐름

```text
Binance klines (ingest_ohlcv, timeframe=config)
  → ohlcv_candle (Postgres)
  → PriceHistoryProvider.get_recent_prices()  → TimesFMPredictor 입력 (close-only)
  → PriceHistoryProvider.get_latest_candle_open_time() → 캔들 close 시 inference 게이트
  → forecast → score → BUY/HOLD/SELL
  → ConsecutiveSignalPolicy (연속 N회)
  → Strategy (TP/SL) → Risk → Exchange
```

엔진 tick 주기(`BINNAIR_MARKET_POLL_INTERVAL_SECONDS`)는 기본적으로 **TimesFM timeframe과 자동 정렬**된다 (`BINNAIR_MARKET_ALIGN_POLL_WITH_TIMEFRAME=true`).

---

## 2. score와 threshold

### score

- TimesFM `horizon` 스텝 point forecast → 현재가 대비 수익률 `forecast_returns`
- `forecast_mode=average`: 스텝 수익률 **산술 평균** (기본값, 권장)
- `forecast_mode=last`: `forecast_index` 한 스텝만 (legacy, 5m에서 과소 신호)

### entry threshold (BUY)

| 우선순위 | 출처 |
|----------|------|
| 1 | `BINNAIR_TIMESFM_SIGNAL_THRESHOLD` (고정값) |
| 2 | `fee_floor × timeframe_scale × horizon_scale` (`timeframe_threshold_scale=true`) |
| 3 | Autopilot ON 시 `percentile(\|score\|) × k` (하한 = 위 entry threshold) |

**fee_floor** = `fee_rate×2 + slippage_rate + safety_margin` (왕복 거래 원가)

**timeframe_scale** (5m 예): `ref_timeframe(1m) / timeframe(5m)` → 긴 봉에서 \|score\|가 작아지는 것을 보정.

### exit threshold (모델 청산)

| 우선순위 | 출처 |
|----------|------|
| 1 | `BINNAIR_TIMESFM_EXIT_SIGNAL_THRESHOLD` |
| 2 | `entry_threshold × BINNAIR_TIMESFM_EXIT_THRESHOLD_MULT` (기본 0.85) |

- **long_only**: SELL 연속 N회 → 롱 청산 (`MODEL_SELL`)
- **long_short**: SELL 연속 N회 → 롱 청산, BUY 연속 N회 → 숏 청산 (`MODEL_BUY`)

청산 threshold는 진입보다 약간 낮아 **조기 exit** 가능 (whipsaw 완화와 trade-off).

---

## 3. 캔들 close 게이트

`BINNAIR_TIMESFM_PREDICT_ON_CANDLE_CLOSE=true` (기본):

- DB `ohlcv_candle` 최신 `open_time`이 바뀐 tick에서만 inference 실행
- 그 외 tick → `hold_reason=awaiting_candle_close` (진입·모델청산 inference 생략, DB 미저장)
- **TP/SL 청산은 매 tick** 그대로 (가격 조건 최우선)

5m 운영 시 60초마다 동일 OHLCV로 중복 inference 하던 문제를 제거.

---

## 4. 입력 시계열 (close-only)

`BINNAIR_TIMESFM_APPEND_LIVE_PRICE_TO_HISTORY=false` (기본):

- DB close 시계열만 TimesFM 입력
- live tick을 close 뒤에 붙이지 않음 (timeframe 혼합 왜곡 방지)

---

## 5. hold_reason (진단)

`model_inference_event.output_prediction.hold_reason`:

| 값 | 의미 |
|----|------|
| `awaiting_candle_close` | 캔들 미갱신 — inference 스킵 |
| `insufficient_context` | OHLCV < min_context |
| `model_unloaded` | TimesFM 로드 실패 |
| `inference_error` | forecast 예외 |
| `below_threshold` | \|score\| ≤ threshold |

API 타임라인 summary: `TimesFM HOLD reason=below_threshold conf=0.19` 형태.

---

## 6. 환경변수 (TimesFM 전용)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BINNAIR_TIMESFM_TIMEFRAME` | `1m` | OHLCV·입력 봉 주기 |
| `BINNAIR_TIMESFM_FORECAST_MODE` | `average` | `average` \| `last` |
| `BINNAIR_TIMESFM_HORIZON` | `3` | forecast 스텝 수 |
| `BINNAIR_TIMESFM_SIGNAL_THRESHOLD` | (자동) | entry 고정 threshold |
| `BINNAIR_TIMESFM_EXIT_THRESHOLD_MULT` | `0.85` | exit = entry × mult |
| `BINNAIR_TIMESFM_TIMEFRAME_THRESHOLD_SCALE` | `true` | timeframe별 threshold 스케일 |
| `BINNAIR_TIMESFM_REF_TIMEFRAME` | `1m` | 스케일 기준 봉 |
| `BINNAIR_TIMESFM_PREDICT_ON_CANDLE_CLOSE` | `true` | 캔들 close inference |
| `BINNAIR_TIMESFM_APPEND_LIVE_PRICE_TO_HISTORY` | `false` | close-only 입력 |
| `BINNAIR_MARKET_ALIGN_POLL_WITH_TIMEFRAME` | `true` | poll ≥ timeframe |
| `BINNAIR_AUTOPILOT_ENABLED` | `false` | adaptive threshold (권장: true) |

---

## 7. 운영 예시 (XRP 5m testnet, long_short)

```bash
BINNAIR_SIGNAL_MODE=long_short
BINNAIR_EXCHANGE_POSITION_SIDE_MODE=ONE_WAY
BINNAIR_TIMESFM_TIMEFRAME=5m
BINNAIR_TIMESFM_FORECAST_MODE=average
BINNAIR_TIMESFM_PREDICT_ON_CANDLE_CLOSE=true
BINNAIR_MARKET_POLL_INTERVAL_SECONDS=300   # align=true면 자동 상향
BINNAIR_AUTOPILOT_ENABLED=true
BINNAIR_SIGNAL_CONSECUTIVE_REQUIRED=2
BINNAIR_RISK_MIN_HOLD_SECONDS_BEFORE_SIGNAL_EXIT=120
```

`signal_threshold`를 수동으로 내리기 전에 **Autopilot + timeframe scale** 조합을 먼저 확인.

---

## 8. 코드 위치

| 모듈 | 역할 |
|------|------|
| `predictor/timesfm_predictor.py` | forecast → action, hold_reason |
| `predictor/timesfm_utils.py` | threshold·timeframe 유틸 |
| `autopilot/calibration.py` | score percentile threshold |
| `engine/core.py` | candle skip, for_exit 분기 |
| `market_data/history.py` | close + latest open_time |

---

## 9. 알려진 한계 / 향후

- quantile head compile만 하고 **uncertainty 필터 미사용** → 구간 폭 기반 HOLD 후보
- zero-shot **심볼별 calibration·백테스트** 스크립트 별도 (`eval_timesfm` TODO)
- `min_context=64`는 wall-clock 창이 timeframe에 비례 — `context_hours` 설정 후보

---

## 10. 관련 문서

- [README.md](../README.md) — 실행·Autopilot·리스크
- [API_REFERENCE.md](./API_REFERENCE.md) — `/autopilot/status`, inference payload
- [PERSISTENCE.md](./PERSISTENCE.md) — `ohlcv_candle`, `model_inference_event`
