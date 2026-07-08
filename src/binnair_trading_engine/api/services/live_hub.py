"""
WebSocket live 스트림 허브 — 클라이언트 구독·상태 캐시·브로드캐스트.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class LiveAccountHub:
    """연결된 WebSocket 클라이언트에 live 계정 이벤트를 fan-out."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._latest_snapshot: dict[str, Any] | None = None
        self._stream_status: dict[str, Any] = {
            "user_stream_connected": False,
            "mark_price_connected": False,
            "last_error": None,
        }

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def get_status(self) -> dict[str, Any]:
        return {
            **self._stream_status,
            "client_count": self.client_count,
            "has_snapshot": self._latest_snapshot is not None,
        }

    async def set_stream_status(self, **kwargs: Any) -> None:
        async with self._lock:
            self._stream_status.update(kwargs)

    async def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        async with self._lock:
            self._latest_snapshot = snapshot

    async def apply_message(self, message: dict[str, Any]) -> None:
        """상태 캐시 갱신 후 브로드캐스트."""
        async with self._lock:
            await self._merge_state_locked(message)
        await self.broadcast(message)

    async def _merge_state_locked(self, message: dict[str, Any]) -> None:
        if self._latest_snapshot is None:
            return
        msg_type = message.get("type")
        if msg_type == "wallet_update":
            wallet = self._latest_snapshot.setdefault("wallet", {})
            for row in message.get("balances") or []:
                if str(row.get("asset", "")).upper() == self._latest_snapshot.get(
                    "quote_asset", "USDT"
                ).upper():
                    wallet["wallet_balance"] = row.get("wallet_balance")
                    wallet["cross_wallet_balance"] = row.get("cross_wallet_balance")
        elif msg_type == "position_update":
            positions = self._latest_snapshot.setdefault("positions", [])
            symbol = message.get("symbol")
            positions[:] = [p for p in positions if p.get("symbol") != symbol]
            positions.append(
                {
                    "symbol": symbol,
                    "side": message.get("side"),
                    "quantity": message.get("quantity"),
                    "entry_price": message.get("entry_price"),
                    "unrealized_profit": message.get("unrealized_pnl"),
                    "leverage": None,
                    "margin_type": message.get("margin_type"),
                }
            )
        elif msg_type == "position_closed":
            symbol = message.get("symbol")
            positions = self._latest_snapshot.setdefault("positions", [])
            self._latest_snapshot["positions"] = [
                p for p in positions if p.get("symbol") != symbol
            ]
        elif msg_type == "mark_price":
            marks = self._latest_snapshot.setdefault("mark_prices", {})
            marks[message.get("symbol")] = message.get("mark_price")

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            snapshot = self._latest_snapshot
            status = dict(self._stream_status)
        if snapshot is not None:
            await ws.send_json(snapshot)
        await ws.send_json({"type": "stream_status", **status})

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            return
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unregister(ws)

    async def send_ping_loop(self, ws: WebSocket, interval: float = 30.0) -> None:
        """클라이언트 keepalive."""
        try:
            while True:
                await asyncio.sleep(interval)
                await ws.send_json({"type": "ping", "event_at": message_event_at()})
        except asyncio.CancelledError:
            raise
        except Exception:
            pass


def message_event_at() -> str:
    from binnair_trading_engine.infra.timezone import now_kst

    return now_kst().isoformat()


_hub: LiveAccountHub | None = None


def get_live_hub() -> LiveAccountHub:
    global _hub
    if _hub is None:
        _hub = LiveAccountHub()
    return _hub
