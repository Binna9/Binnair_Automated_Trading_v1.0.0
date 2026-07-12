# BinnAIR UI 연동 가이드 — 런타임 설정 & 매매 Start/Stop

> **대상:** 프론트엔드 / UI 개발자  
> **버전:** v1.2 (2026-07)  
> **관련 문서:** [API_REFERENCE.md](./API_REFERENCE.md), [PERSISTENCE.md](./PERSISTENCE.md)

---

## 1. 한 줄 요약

- API는 **L1 전체 파라미터(~45개)** 를 PUT/POST body로 받는다.
- UI는 **`GET /control/schema`의 `tier`** 로 **기본 / 고급** 폼을 나눈다.
- Start/Stop = **매매 on/off** (프로세스 종료 아님).

```
기본 화면 (tier=basic, 9개)  ─┐
고급 모드 (tier=advanced)   ─┼─▶ PUT/POST (전체 필드 허용) ─▶ DB ─▶ 엔진
env 전용 (env_only_keys)    ─┘   (UI에서 숨김, API 미수신)
```

---

## 2. UI 폼 구성 — 기본 vs 고급

`GET /api/v1/control/schema` 응답:

```json
{
  "params": [
    { "key": "symbol", "tier": "basic", "group": "market", "type": "string", "label": "거래 심볼", ... },
    { "key": "risk_daily_loss_limit_pct", "tier": "advanced", ... }
  ],
  "basic_keys": ["symbol", "signal_mode", ...],
  "advanced_keys": ["poll_interval_seconds", "risk_daily_loss_limit_pct", ...],
  "env_only_keys": ["exchange.api_key", ...]
}
```

### 기본 화면 (`tier: "basic"` — 9개)

| 키 | 라벨 | 비고 |
|----|------|------|
| `symbol` | 거래 심볼 | |
| `signal_mode` | 매매 모드 | `long_only` \| `long_short` |
| `signal_consecutive_required` | 연속 신호 횟수 | |
| `timesfm_timeframe` | 캔들 주기 | `5m` 등. 변경 시 재시작 권장 |
| `leverage` | 레버리지 | |
| `autopilot_enabled` | Autopilot | |
| `autopilot_score_percentile` | 진입 민감도 | Autopilot on |
| `trade_tp_pct` | 익절 % | Autopilot off |
| `trade_sl_pct` | 손절 % | Autopilot off |

### 고급 모드 (`tier: "advanced"` — 나머지 L1)

run_id, strategy_id, poll_interval, margin_type, oco, sizing 4종, risk 8종, timesfm 세부, autopilot ATR/레짐 파라미터 등.  
`params` 배열에서 `tier === "advanced"` 필터로 폼 생성.

### env 전용 (`env_only_keys` — UI 미표시)

API 키, DB, HF 모델 ID, EMA 레짐 내부 상수 등. 폼에 넣지 않음.

### UI 표시 규칙

```
autopilot_enabled === true
  → trade_tp_pct / trade_sl_pct 비활성 또는 숨김
  → autopilot_score_percentile 활성

autopilot_enabled === false
  → 반대
```

---

## 3. Start / Stop

### 전제
- Docker/서버 **프로세스 기동** = 엔진 프로세스만 올라감 (tick·명령 poll은 동작).
- **기동 직후 매매는 꺼져 있음:** `trading_enabled=false`, `engine_run.status=paused`.
- **UI 「매매 시작」** 을 눌러야 실제 주문·진입이 시작된다.
- 버튼: **「매매 시작」** / **「매매 중지」** (프로세스 kill 아님)

| 동작 | API |
|------|-----|
| 매매 중지 | `POST /api/v1/control/stop` |
| 설정 저장만 | `PUT /api/v1/control/config` |
| 저장 + 매매 시작 | `POST /api/v1/control/start` |
| 상태 | `GET /api/v1/control/status` |

**Body:** `RuntimeConfigParams` — **전체 필드 optional**. 기본+고급 합쳐서내도 됨.

```http
POST /api/v1/control/start?user_id=default
Content-Type: application/json

{
  "symbol": "XRPUSDT",
  "signal_mode": "long_short",
  "timesfm_timeframe": "5m",
  "leverage": 2,
  "autopilot_enabled": true,
  "autopilot_score_percentile": 70,
  "risk_min_hold_seconds_before_signal_exit": 120
}
```

Stop 후 고급 모드에서 risk만 바꾸고 Start해도 동일 API.

---

## 4. GET 응답 구조

`/config`, `/status`, PUT/POST 응답 공통:

| 필드 | 설명 |
|------|------|
| `config` | 전체 effective 값 (flat, ~45키) |
| `config_basic` | 기본 9개만 |
| `config_advanced` | 고급만 |
| `trading_enabled` | 매매 on/off (UI 기준 **이걸 보면 됨**) |
| `engine_run.status` | `running` \| `paused` \| `stopped` \| `error` — Stop 후 `paused` |
| `engine_run.status_meaning` | 한글 설명 (status API) |
| `config_version` | revision |
| `recent_commands` | start/stop 처리 상태 (`status`: `pending`\|`done`\|`failed`) |

폼 초기값: `config_basic`로 기본 탭, 고급 탭은 `config_advanced`.

---

## 5. 권장 UI 플로우

```
화면 로드 → GET /control/schema (폼 메타)
         → GET /control/status (값 + trading_enabled)

[매매 중지] → POST /stop
폼 수정 (기본 + 선택적 고급)
[매매 시작] → POST /start { 변경 필드만 or 전체 }
         → GET /status 폴링 until recent_commands[0].status === "done"
```

---

## 6. TypeScript 예시

```typescript
type ParamTier = "basic" | "advanced";

interface SchemaParam {
  key: string;
  tier: ParamTier;
  group: string;
  type: string;
  label: string;
  hint?: string;
  options?: string[];
}

async function loadSchema() {
  const r = await fetch(`${BASE}/api/v1/control/schema`);
  const { params, basic_keys, advanced_keys } = await r.json();
  const basicFields = params.filter((p: SchemaParam) => p.tier === "basic");
  const advancedFields = params.filter((p: SchemaParam) => p.tier === "advanced");
  return { basicFields, advancedFields, basic_keys, advanced_keys };
}

async function loadStatus() {
  const r = await fetch(`${BASE}/api/v1/control/status?user_id=default`);
  const data = await r.json();
  return {
    tradingEnabled: data.trading_enabled,
    basic: data.config_basic,
    advanced: data.config_advanced,
    full: data.config,
  };
}

// Start — 기본+고급 합쳐서 전송
async function startTrading(values: Record<string, unknown>) {
  await fetch(`${BASE}/api/v1/control/start?user_id=default`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
}
```

---

## 7. 주의사항

| 항목 | 내용 |
|------|------|
| Stop | 신규 진입만 중지. `engine_run.status` → **`paused`** (프로세스는 유지) |
| symbol / timeframe | 저장은 즉시, OHLCV ingest는 **재시작** 필요할 수 있음 |
| 명령 반영 | poll 주기(최대 ~300초) 지연 가능 |
| sizing / predictor | 일부는 DB 저장 후 **hot-reload 제한** — 고급 변경 후 재시작 권장 문구 |

---

## 8. 배포 체크리스트

- [ ] `python scripts/init_db.py`
- [ ] `trading-api` / `trading-engine` 최신 배포
- [ ] Postgres `BINNAIR_STORAGE_BACKEND=postgres`

---

*v1.2: API 전체 수신 + schema `tier`로 UI 기본/고급 분리.*
