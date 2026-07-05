"""
Binance Futures WebSocket 이벤트 → 프론트용 live 메시지 변환.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from binnair_trading_engine.infra.timezone import now_kst


def _ts_ms(event_ms: int | None) -> str:
    if not event_ms:
        return now_kst().isoformat()
    return datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc).astimezone(
        now_kst().tzinfo
    ).isoformat()


def parse_user_stream_event(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """단일 User Data Stream JSON → 0..N live 메시지."""
    event_type = raw.get("e")
    if event_type == "ACCOUNT_UPDATE":
        return _parse_account_update(raw)
    if event_type == "ORDER_TRADE_UPDATE":
        msg = _parse_order_trade_update(raw)
        return [msg] if msg else []
    if event_type == "listenKeyExpired":
        return [{"type": "stream_error", "code": "listen_key_expired", "message": "listenKey expired"}]
    return []


def _parse_account_update(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    event_ts = _ts_ms(raw.get("E"))
    account = raw.get("a") or {}
    reason = account.get("m", "")

    balances = account.get("B") or []
    if balances:
        wallet_balances = []
        for row in balances:
            asset = str(row.get("a", ""))
            wallet_balances.append(
                {
                    "asset": asset,
                    "wallet_balance": float(row.get("wb", 0) or 0),
                    "cross_wallet_balance": float(row.get("cw", 0) or 0),
                    "balance_change": float(row.get("bc", 0) or 0),
                }
            )
        out.append(
            {
                "type": "wallet_update",
                "reason": reason,
                "event_at": event_ts,
                "balances": wallet_balances,
            }
        )

    positions = account.get("P") or []
    for row in positions:
        amt = float(row.get("pa", 0) or 0)
        if amt == 0:
            out.append(
                {
                    "type": "position_closed",
                    "symbol": row.get("s", ""),
                    "position_side": row.get("ps", "BOTH"),
                    "margin_type": row.get("mt", ""),
                    "reason": reason,
                    "event_at": event_ts,
                }
            )
            continue
        side = "LONG" if amt > 0 else "SHORT"
        out.append(
            {
                "type": "position_update",
                "symbol": row.get("s", ""),
                "side": side,
                "quantity": abs(amt),
                "entry_price": float(row.get("ep", 0) or 0),
                "unrealized_pnl": float(row.get("up", 0) or 0),
                "position_side": row.get("ps", "BOTH"),
                "margin_type": row.get("mt", ""),
                "reason": reason,
                "event_at": event_ts,
            }
        )
    return out


def _parse_order_trade_update(raw: dict[str, Any]) -> dict[str, Any] | None:
    order = raw.get("o") or {}
    status = str(order.get("X", ""))
    if not status:
        return None
    return {
        "type": "order_update",
        "symbol": order.get("s", ""),
        "side": order.get("S", ""),
        "order_type": order.get("o", ""),
        "status": status,
        "order_id": str(order.get("i", "")),
        "client_order_id": order.get("c", ""),
        "quantity": float(order.get("q", 0) or 0),
        "executed_qty": float(order.get("z", 0) or 0),
        "avg_price": float(order.get("ap", 0) or 0),
        "last_fill_price": float(order.get("L", 0) or 0),
        "last_fill_qty": float(order.get("l", 0) or 0),
        "reduce_only": bool(order.get("R", False)),
        "position_side": order.get("ps", "BOTH"),
        "realized_pnl": float(order.get("rp", 0) or 0),
        "event_at": _ts_ms(raw.get("E")),
    }


def parse_mark_price_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    if raw.get("e") != "markPriceUpdate":
        return None
    symbol = raw.get("s", "")
    price = float(raw.get("p", 0) or 0)
    if not symbol or price <= 0:
        return None
    return {
        "type": "mark_price",
        "symbol": symbol,
        "mark_price": price,
        "funding_rate": float(raw.get("r", 0) or 0),
        "event_at": _ts_ms(raw.get("E")),
    }


def build_snapshot_from_wallet_api(
    wallet: dict[str, Any],
    *,
    quote_asset: str,
    symbol: str | None = None,
) -> dict[str, Any]:
    """fetch_wallet_info() 결과 → WebSocket snapshot 메시지."""
    account = wallet.get("account") or {}
    positions = wallet.get("positions") or []
    if symbol:
        sym = symbol.upper()
        positions = [p for p in positions if str(p.get("symbol", "")).upper() == sym]

    quote = quote_asset.upper()
    available = float(account.get("available_balance", 0) or 0)
    for row in wallet.get("balances") or []:
        if str(row.get("asset", "")).upper() == quote:
            available = float(row.get("available_balance", available) or available)
            break

    return {
        "type": "snapshot",
        "event_at": now_kst().isoformat(),
        "environment": wallet.get("environment"),
        "paper_mode": bool(wallet.get("paper_mode")),
        "market_type": wallet.get("market_type"),
        "base_url": wallet.get("base_url"),
        "quote_asset": quote,
        "wallet": {
            "available_balance": available,
            "total_wallet_balance": float(account.get("total_wallet_balance", 0) or 0),
            "total_unrealized_profit": float(account.get("total_unrealized_profit", 0) or 0),
            "total_margin_balance": float(account.get("total_margin_balance", 0) or 0),
            "can_trade": bool(account.get("can_trade", False)),
        },
        "positions": [
            {
                "symbol": p.get("symbol"),
                "side": "LONG" if float(p.get("position_amt", 0) or 0) > 0 else "SHORT",
                "quantity": abs(float(p.get("position_amt", 0) or 0)),
                "entry_price": float(p.get("entry_price", 0) or 0),
                "unrealized_profit": float(p.get("unrealized_profit", 0) or 0),
                "leverage": int(float(p.get("leverage", 0) or 0)),
                "margin_type": p.get("margin_type"),
            }
            for p in positions
            if float(p.get("position_amt", 0) or 0) != 0
        ],
        "stream": wallet.get("stream") or {},
    }
