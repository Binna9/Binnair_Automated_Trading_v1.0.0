# BinnAIR Live WebSocket API — 프론트엔드 연동 가이드

> **실시간** 지갑·포지션·체결 이벤트. REST `GET /account/wallet`은 **초기 스냅샷/폴백**용.  
> DB 이력(시그널·주문)은 기존 REST 그대로 사용.

---

## 1. 개요

| 항목 | 값 |
|------|-----|
| WebSocket URL | `ws://127.0.0.1:8000/ws/v1/live` |
| REST 스냅샷 | `GET /api/v1/account/wallet` |
| 스트림 상태 | `GET /api/v1/live/status` |
| 프로토콜 | JSON text frame |
| Auth | v1 없음 (로컬/사내망 전제) |

### testnet ↔ mainnet 전환

**프론트 코드 변경 없음.** 서버 `config.yaml`:

```yaml
exchange:
  paper_mode: false
  base_url: "https://testnet.binancefuture.com"   # testnet
  # base_url: "https://fapi.binance.com"          # mainnet
```

서버가 `base_url`에 맞춰 Binance WebSocket URL을 자동 선택한다.

| environment | REST | WebSocket (fstream) |
|-------------|------|---------------------|
| `futures_testnet` | testnet.binancefuture.com | wss://fstream.binancefuture.com |
| `futures_mainnet` | fapi.binance.com | wss://fstream.binance.com |
| `paper` | (없음) | REST 폴링 모드 (~5초) |

`snapshot.environment` 필드로 현재 모드를 표시한다.

---

## 2. 연결 흐름

```
1. WebSocket connect → ws://host:8000/ws/v1/live
2. 서버 → snapshot (전체 지갑·포지션)
3. 서버 → stream_status (User Stream / mark price 연결 상태)
4. 체결·잔고 변동 시 → wallet_update / position_update / order_update push
5. mark price tick → mark_price (미실현 PnL UI 갱신용)
6. (선택) 클라이언트 → {"action":"refresh"} → REST 재조회 후 snapshot 재전송
```

### JavaScript 예시

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/ws/v1/live");

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "snapshot":
      renderWallet(msg.wallet);
      renderPositions(msg.positions);
      break;
    case "position_update":
      upsertPosition(msg);
      break;
    case "order_update":
      if (msg.status === "FILLED") toastFill(msg);
      break;
    case "mark_price":
      updateMarkPrice(msg.symbol, msg.mark_price);
      break;
    case "ping":
      ws.send(JSON.stringify({ action: "pong" }));
      break;
  }
};

// 수동 새로고침
function refreshWallet() {
  ws.send(JSON.stringify({ action: "refresh" }));
}
```

---

## 3. 메시지 타입

### 3.1 `snapshot` (연결 직후 + refresh)

```json
{
  "type": "snapshot",
  "event_at": "2026-07-05T18:00:00+09:00",
  "environment": "futures_testnet",
  "paper_mode": false,
  "market_type": "futures",
  "base_url": "https://testnet.binancefuture.com",
  "quote_asset": "USDT",
  "wallet": {
    "available_balance": 4497.59,
    "total_wallet_balance": 5001.20,
    "total_unrealized_profit": -0.42,
    "total_margin_balance": 5000.78,
    "can_trade": true
  },
  "positions": [
    {
      "symbol": "XRPUSDT",
      "side": "LONG",
      "quantity": 877.9,
      "entry_price": 1.141,
      "unrealized_profit": -0.35,
      "leverage": 2,
      "margin_type": "isolated"
    }
  ],
  "stream": {
    "ws_base": "wss://fstream.binancefuture.com",
    "user_stream_enabled": true,
    "mark_price_enabled": true,
    "symbol": "XRPUSDT"
  }
}
```

### 3.2 `stream_status`

```json
{
  "type": "stream_status",
  "user_stream_connected": true,
  "mark_price_connected": true,
  "client_count": 1,
  "last_error": null
}
```

### 3.3 `wallet_update`

Binance `ACCOUNT_UPDATE` 잔고 변동.

```json
{
  "type": "wallet_update",
  "reason": "ORDER",
  "event_at": "2026-07-05T18:01:00+09:00",
  "balances": [
    {
      "asset": "USDT",
      "wallet_balance": 5000.5,
      "cross_wallet_balance": 5000.5,
      "balance_change": -1.2
    }
  ]
}
```

### 3.4 `position_update`

```json
{
  "type": "position_update",
  "symbol": "XRPUSDT",
  "side": "LONG",
  "quantity": 877.9,
  "entry_price": 1.141,
  "unrealized_pnl": -0.35,
  "position_side": "BOTH",
  "margin_type": "isolated",
  "reason": "ORDER",
  "event_at": "2026-07-05T18:01:00+09:00"
}
```

### 3.5 `position_closed`

수량 0으로 업데이트된 경우.

```json
{
  "type": "position_closed",
  "symbol": "XRPUSDT",
  "position_side": "BOTH",
  "reason": "ORDER",
  "event_at": "2026-07-05T18:05:00+09:00"
}
```

### 3.6 `order_update`

Binance `ORDER_TRADE_UPDATE`.

```json
{
  "type": "order_update",
  "symbol": "XRPUSDT",
  "side": "BUY",
  "order_type": "MARKET",
  "status": "FILLED",
  "order_id": "2346820116",
  "quantity": 877.9,
  "executed_qty": 877.9,
  "avg_price": 1.141,
  "reduce_only": false,
  "realized_pnl": 0,
  "event_at": "2026-07-05T18:01:00+09:00"
}
```

### 3.7 `mark_price`

```json
{
  "type": "mark_price",
  "symbol": "XRPUSDT",
  "mark_price": 1.1398,
  "funding_rate": 0.0001,
  "event_at": "2026-07-05T18:01:01+09:00"
}
```

미실현 PnL UI (클라이언트 계산 예):

```
LONG: (mark_price - entry_price) * quantity
```

### 3.8 `ping` / 클라이언트 `pong`

서버 30초마다 `ping` → 클라이언트 `{"action":"pong"}` (선택).

### 3.9 `stream_error`

```json
{
  "type": "stream_error",
  "code": "listen_key_expired",
  "message": "listenKey expired"
}
```

서버가 자동 재연결한다. UI에 “재연결 중” 표시 권장.

---

## 4. REST 보조 API

### `GET /api/v1/account/wallet`

WebSocket 연결 전 초기 데이터, 또는 WS 장애 시 폴백 폴링.

추가 필드:

| 필드 | 설명 |
|------|------|
| `environment` | `futures_testnet` \| `futures_mainnet` \| `paper` |
| `stream.ws_base` | Binance fstream URL |
| `stream.mark_price_stream` | 구독 중인 mark price 채널 |

### `GET /api/v1/live/status`

```json
{
  "ok": true,
  "user_stream_connected": true,
  "mark_price_connected": true,
  "client_count": 2,
  "has_snapshot": true,
  "last_error": null
}
```

---

## 5. UI 권장 구성

```
┌─────────────────────────────────────────────┐
│  LIVE ●  futures_testnet   WS connected      │
├─────────────────────────────────────────────┤
│  USDT Available    4,497.59                  │
│  Wallet Total      5,001.20                  │
│  Unrealized PnL      -0.42                   │
├─────────────────────────────────────────────┤
│  XRPUSDT LONG  877.9 @ 1.141                 │
│  Mark 1.1398   uPnL -1.05                    │
├─────────────────────────────────────────────┤
│  Recent fills (order_update FILLED)          │
└─────────────────────────────────────────────┘
```

| 데이터 | 소스 |
|--------|------|
| 지갑·포지션 실시간 | **WebSocket** |
| mark price | **WebSocket** `mark_price` |
| 시그널·주문 이력 | REST `/flow/timeline` |
| 성과 KPI | REST `/performance/*` |

**폴링 가이드 변경:** 대시보드 wallet 영역은 WS 전환 후 **5~10초 REST 폴링 제거**. DB 타임라인만 10~30초 폴링.

---

## 6. 서버 설정 (`config.yaml`)

```yaml
api:
  enabled: true
  host: "127.0.0.1"
  port: 8000
  live_stream:
    enabled: true
    mark_price_enabled: true
    listen_key_keepalive_seconds: 1800
    reconnect_delay_seconds: 5.0
```

### API 서버 실행

```bash
CONFIG_PATH=config/config.yaml .venv/bin/python scripts/run_api.py
# 또는
CONFIG_PATH=config/config.yaml .venv/bin/binnair-api
```

엔진(`run_engine.py`)과 **별도 프로세스**. API만 켜도 live stream 동작 (같은 config의 exchange 키 사용).

---

## 7. 장애·폴백

| 상황 | 동작 |
|------|------|
| WS disconnect | 서버 자동 재연결 (`reconnect_delay_seconds`) |
| listenKey 만료 | 재발급 후 재구독 |
| `paper_mode: true` | Binance WS 없음, ~5초 REST snapshot 폴링 |
| WS unavailable | 프론트 `GET /account/wallet` 5초 폴링 폴백 |

---

## 8. 보안 (운영 시)

- v1: API Key는 **서버 config만** — 프론트에 노출 금지
- mainnet 전환 시 HTTPS/WSS + API IP whitelist 권장
- 추후: JWT로 `/ws/v1/live` 보호

---

## 9. 관련 문서

- [API_REFERENCE.md](./API_REFERENCE.md) — REST 전체 목록
- [API_FRONTEND.md](./API_FRONTEND.md) — 화면별 REST 매핑
