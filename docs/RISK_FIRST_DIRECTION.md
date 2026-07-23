# 리스크 우선 방향 (Risk-First Direction)

> 운영 진단 + 아키텍처 합의 + 진행 로드맵  
> 기준일: 2026-07-23 · run_id=`prod_timesfm_run` (Futures Testnet)

---

## 1. 운영 진단 요약

| 항목 | 관측 |
|------|------|
| 엔진 | running, `trading_enabled=true`, XRPUSDT 5m long_short |
| 실거래 | 약 42건 (유령 제외), 실현손익 ≈ **−13.2 USDT (−0.27%)** |
| 승률 | ≈ 45% |
| STOP_LOSS | 실 20건 ≈ **−94.6** (손실의 본체) |
| TAKE_PROFIT / MODEL_* | 흑자 구간 |
| Autopilot | 엔진 state 정상 (`high_vol`, tick 진행). API는 state 볼륨 마운트 후 `available=true` |
| 유령 기록 | `|pnl|<0.01` 약 11건 — 거래소 dust 복구로 통계 오염 |

**결론:** 시스템은 “돌아간다”. 손익 병목은 TimesFM 정확도가 아니라 **청산(SL)·리스크 구조**다.

---

## 2. 아키텍처 판정

### 이전(암묵적) 모델
```text
TimesFM = 매매 판단 중축
→ consecutive → 주문 → TP/SL
```

### 문제
- TimesFM은 범용 시계열 foundation이지 **비용·레짐·포지션을 학습한 트레이딩 의사결정기**가 아님.
- 예측 정확도 ≠ 매매 엣지. 운영에서 TP·모델청산은 +인데 SL이 −를 만듦.
- “더 정확한 foundation 가중치”에 중축을 맡기면, 학습·검증 루프가 뒤로 밀림.

### 합의된 모델
```text
TimesFM (및 향후 커스텀 모델) = 약한 soft signal / score 후보
Risk + Exit + Validation     = 강한 hard gate (일관 규칙)
목표 = 예측 실패해도 파산·구조적 적자 장사를 하지 않음
     (개별 무손실이 아님 — expectancy·하방 통제)
```

커스텀 학습 파이프(수집→전처리→피처→학습)는 **폐기하지 않는다**.  
오프라인에서 TimesFM과 **동일 라벨·비용**으로 비교한 뒤 중축 후보를 결정한다.

---

## 3. 시스템 원칙

1. **약한 시그널** — 예측은 진입 후보만. 단독 최종 권한이 아님.
2. **강한 리스크** — 일손실·연속손절·명목·중복·(향후) 레짐 게이트가 최종 거부권.
3. **검증 없이 파라미터 금지** — 감으로 SL/threshold를 동시에 여러 개 바꾸지 않음.
4. **데이터 하이진** — dust·유령·중복을 실거래 집계에서 제외/차단.
5. **한 스텝씩** — 하이진 → 구조 → 리스크 규칙 강화 → 연구 레이어.

---

## 4. 이미 한 일

| 항목 | 상태 |
|------|------|
| trading-api에 engine state 볼륨 마운트 | 운영 compose (`available=true`) |
| dust 복구 무시 + `trade_result` min notional 스킵 | 코드 (**엔진 재배포 필요**) |
| entry soft/hard 경계 1차 리팩터 | Phase 1 완료 |
| high_vol 진입 축소 (scale 0.5, consec +2) | Phase 2-a 코드 반영 (**엔진 재배포 필요**) |

---

## 5. 로드맵

### Phase 0 — Hygiene (완료)
- dust 유령 `trade_result` 차단
- 실거래만으로 PnL·승률 집계

### Phase 1 — Structure (완료)
- soft signal vs hard risk 코드 경계 명시
- 리스크 거부 시 audit 일관 기록
- Predictor = soft candidate 역할 문서화

### Phase 2 — Risk rules (진행 중)
- **2-a (이번):** `high_vol` 진입 축소만  
  - `position_scale` 0.7 → **0.5**  
  - `consecutive_delta` +1 → **+2** (base 2면 high_vol에서 consecutive=4)  
  - threshold_mult 1.5 유지  
  - 설정키: `autopilot_high_vol_position_scale` / `_consecutive_delta` / `_threshold_mult`  
  - **SL ATR 배수는 이번 턴에 안 건드림** (원인 분리)
- **2-b (다음 후보):** 연속손절·일손실 게이트 강화 (숫자 하나씩)

### Phase 3 — Validation / Research
- 라이브와 동일 규칙 오프라인 재현
- expectancy, MDD, 레짐별 PnL, 진입 vs 청산 attribution
- TimesFM vs 커스텀 가중치 walk-forward 비교

---

## 5.1 운영 배포 (당신이 할 일)

코드는 로컬 리포에만 반영됨. 라이브 반영 순서:

```bash
# 1) 이 리포 push / CI로 trading-engine 이미지 빌드
# 2) 서버에서
cd ~/apps/binnair-stack
docker compose pull trading-engine   # 또는 사용 중인 dc
docker compose up -d trading-engine

# 3) 확인 — high_vol 이면 scale≈0.5, consecutive≈ base+2
docker exec trading-engine cat /data/state/autopilot_state.json | head -40
curl -s 'http://127.0.0.1:8001/api/v1/autopilot/status?run_id=prod_timesfm_run'
```

배포 후 며칠은 **거래 수·SL 건수·일 PnL**만 본다. SL 폭은 아직 안 바꿨다.

---

## 6. 성공 지표

| 지표 | 용도 |
|------|------|
| 실거래 expectancy (유령 제외) | 구조적 적자 여부 |
| Max drawdown / 일손실 히트 횟수 | 하방 통제 |
| STOP_LOSS 비중·평균 손실% | 청산 품질 |
| 레짐별 PnL (`high_vol` 등) | AP·리스크 게이트 효과 |
| risk_rejected audit 비율 | 리스크가 실제로 막는 빈도 |

시그널 적중률만으로 성공을 정의하지 않는다.

---

## 7. 관련 코드

- 진입 soft/hard: `src/binnair_trading_engine/engine/entry_pipeline.py`
- 엔진 오케스트레이션: `src/binnair_trading_engine/engine/core.py`
- 리스크: `src/binnair_trading_engine/risk/default.py`
- dust 필터: `performance/metrics.py` + `engine/core.py` `_is_dust_notional`
