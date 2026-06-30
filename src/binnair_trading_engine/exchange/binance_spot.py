"""
Binance Spot REST API 어댑터다.
현물 주문, 취소, 주문 상태, 체결 내역 조회를 담당한다.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from binnair_trading_engine.domain.models import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
)
from binnair_trading_engine.exchange.interface import ExchangeAdapter

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.binance.com"


def _symbol_to_base(symbol: str) -> str:
    """BTCUSDT -> BTC, ETHUSDT -> ETH."""
    for q in ("USDT", "BUSD", "USD"):
        if symbol.endswith(q):
            return symbol[: -len(q)]
    return symbol


def _sign(query: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class BinanceSpotAdapter(ExchangeAdapter):
    """
    Binance Spot REST API 실거래 어댑터.
    API Key / Secret 필수.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = True,
    ) -> dict:
        params = dict(params) if params else {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query = urlencode(sorted(params.items()))
            params["signature"] = _sign(query, self._api_secret)
            query = urlencode(sorted(params.items()))
        else:
            query = urlencode(params) if params else ""

        url = f"{self._base_url}{path}" + ("?" + query if query else "")
        headers = {"X-MBX-APIKEY": self._api_key}

        resp = httpx.request(
            method,
            url,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def place_order(self, order: Order) -> Order:
        """주문 실행. MARKET/LIMIT 지원."""
        params: dict = {
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": self._format_qty(order.symbol, order.quantity),
        }
        if order.order_type == OrderType.LIMIT:
            if order.price is None:
                raise ValueError("LIMIT order requires price")
            params["price"] = self._format_price(order.symbol, order.price)
            params["timeInForce"] = "GTC"

        try:
            data = self._request("POST", "/api/v3/order", params)
        except httpx.HTTPStatusError as e:
            logger.exception("Binance order failed: %s", e)
            order.status = OrderStatus.REJECTED
            return order

        order.order_id = str(data.get("orderId", ""))
        order.client_order_id = data.get("clientOrderId") or order.client_order_id
        status = data.get("status", "").upper()
        order.status = self._map_status(status)
        exec_qty = float(data.get("executedQty", 0) or 0)
        cum_quote = float(data.get("cummulativeQuoteQty", 0) or 0)
        if exec_qty > 0 and cum_quote > 0:
            order.price = cum_quote / exec_qty
        elif data.get("price"):
            order.price = float(data["price"])
        if exec_qty > 0:
            order.quantity = exec_qty

        return order

    def _format_qty(self, symbol: str, qty: float) -> str:
        """거래소 lot size 맞춤. 기본 8자리."""
        return f"{qty:.8f}".rstrip("0").rstrip(".")

    def _format_price(self, symbol: str, price: float) -> str:
        return f"{price:.8f}".rstrip("0").rstrip(".")

    def _map_status(self, status: str) -> OrderStatus:
        m = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }
        return m.get(status, OrderStatus.PENDING)

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            self._request("DELETE", "/api/v3/order", {"symbol": symbol, "orderId": order_id})
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("Binance cancel failed: %s", e)
            return False

    def get_position(self, symbol: str) -> Position | None:
        base = _symbol_to_base(symbol)
        try:
            data = self._request("GET", "/api/v3/account")
        except httpx.HTTPStatusError as e:
            logger.warning("Binance account failed: %s", e)
            return None

        for b in data.get("balances", []):
            if b.get("asset") == base:
                free = float(b.get("free", 0))
                locked = float(b.get("locked", 0))
                qty = free + locked
                if qty <= 0:
                    return None
                return Position(
                    symbol=symbol,
                    quantity=qty,
                    avg_entry_price=0.0,
                    updated_at=datetime.now(timezone.utc),
                )
        return None

    def get_all_positions(self) -> list[Position]:
        """현재 심볼들 포지션. account에서 잔고>0인 base asset만."""
        try:
            data = self._request("GET", "/api/v3/account")
        except httpx.HTTPStatusError as e:
            logger.warning("Binance account failed: %s", e)
            return []

        out: list[Position] = []
        for b in data.get("balances", []):
            asset = b.get("asset", "")
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            qty = free + locked
            if qty <= 0 or asset in ("USDT", "BUSD", "USD", "BNB"):
                continue
            symbol = f"{asset}USDT"
            out.append(
                Position(
                    symbol=symbol,
                    quantity=qty,
                    avg_entry_price=0.0,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return out

    def get_order(self, symbol: str, order_id: str) -> Order | None:
        try:
            data = self._request("GET", "/api/v3/order", {"symbol": symbol, "orderId": order_id})
        except httpx.HTTPStatusError:
            return None

        return Order(
            symbol=data.get("symbol", symbol),
            side=OrderSide(data.get("side", "BUY")),
            order_type=OrderType(data.get("type", "MARKET")),
            quantity=float(data.get("executedQty", data.get("origQty", 0))),
            price=float(data["price"]) if data.get("price") else None,
            status=self._map_status(data.get("status", "")),
            order_id=str(data.get("orderId", "")),
            client_order_id=data.get("clientOrderId"),
        )

    def get_recent_trades(self, symbol: str, limit: int = 10) -> list[Trade]:
        try:
            data = self._request("GET", "/api/v3/myTrades", {"symbol": symbol, "limit": limit})
        except httpx.HTTPStatusError:
            return []

        out: list[Trade] = []
        for t in data:
            out.append(
                Trade(
                    trade_id=str(t.get("id", "")),
                    order_id=str(t.get("orderId", "")),
                    symbol=symbol,
                    side=OrderSide.BUY if t.get("isBuyer") else OrderSide.SELL,
                    quantity=float(t.get("qty", 0)),
                    price=float(t.get("price", 0)),
                    commission=float(t.get("commission", 0)),
                )
            )
        return out
