"""
Binance USD-M Futures REST API 어댑터다.
테스트넷/실거래 선물 주문, 잔고, 포지션, TP/SL 보호 주문 조회와 실행을 담당한다.
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

DEFAULT_FUTURES_BASE_URL = "https://fapi.binance.com"


def _sign(query: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class BinanceFuturesAdapter(ExchangeAdapter):
    """Binance USD-M Futures 어댑터."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_FUTURES_BASE_URL,
        leverage: int = 3,
        margin_type: str = "ISOLATED",
        position_side_mode: str = "ONE_WAY",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._default_leverage = max(1, int(leverage))
        self._margin_type = margin_type.upper()
        self._position_side_mode = position_side_mode.upper()
        self._symbol_prepared: set[str] = set()

    @property
    def manages_exit_orders(self) -> bool:
        return True

    def get_available_balance(self, asset: str = "USDT") -> float:
        """Futures 계정의 주문 가능 잔고(availableBalance)를 조회한다."""
        try:
            data = self._request("GET", "/fapi/v2/balance")
        except httpx.HTTPStatusError as e:
            logger.warning("Binance futures balance fetch failed: %s", e)
            return 0.0
        if not isinstance(data, list):
            return 0.0
        target = asset.upper()
        for row in data:
            if str(row.get("asset", "")).upper() == target:
                return float(row.get("availableBalance", 0) or 0.0)
        return 0.0

    def fetch_wallet_snapshot(self) -> dict:
        """모니터 API용 read-only 지갑·포지션 스냅샷."""
        snapshot: dict = {
            "market_type": "futures",
            "base_url": self._base_url,
            "ok": False,
            "error": None,
            "balances": [],
            "account": {},
            "positions": [],
        }
        try:
            raw_balances = self._request("GET", "/fapi/v2/balance")
            raw_account = self._request("GET", "/fapi/v2/account")
            raw_positions = self._request("GET", "/fapi/v2/positionRisk")
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text
            except Exception:
                pass
            snapshot["error"] = {
                "type": "http_error",
                "status_code": e.response.status_code,
                "message": str(e),
                "body": body[:1000],
            }
            return snapshot

        if isinstance(raw_balances, list):
            snapshot["balances"] = [
                {
                    "asset": row.get("asset"),
                    "balance": float(row.get("balance", 0) or 0),
                    "cross_wallet_balance": float(
                        row.get("crossWalletBalance", 0) or 0
                    ),
                    "available_balance": float(
                        row.get("availableBalance", 0) or 0
                    ),
                    "max_withdraw_amount": float(
                        row.get("maxWithdrawAmount", 0) or 0
                    ),
                }
                for row in raw_balances
                if float(row.get("balance", 0) or 0) > 0
                or float(row.get("availableBalance", 0) or 0) > 0
            ]

        if isinstance(raw_account, dict):
            snapshot["account"] = {
                "total_wallet_balance": float(
                    raw_account.get("totalWalletBalance", 0) or 0
                ),
                "total_unrealized_profit": float(
                    raw_account.get("totalUnrealizedProfit", 0) or 0
                ),
                "total_margin_balance": float(
                    raw_account.get("totalMarginBalance", 0) or 0
                ),
                "available_balance": float(
                    raw_account.get("availableBalance", 0) or 0
                ),
                "max_withdraw_amount": float(
                    raw_account.get("maxWithdrawAmount", 0) or 0
                ),
                "can_trade": bool(raw_account.get("canTrade", False)),
                "can_deposit": bool(raw_account.get("canDeposit", False)),
                "can_withdraw": bool(raw_account.get("canWithdraw", False)),
            }

        if isinstance(raw_positions, list):
            snapshot["positions"] = [
                {
                    "symbol": row.get("symbol"),
                    "position_side": row.get("positionSide"),
                    "position_amt": float(row.get("positionAmt", 0) or 0),
                    "entry_price": float(row.get("entryPrice", 0) or 0),
                    "unrealized_profit": float(row.get("unRealizedProfit", 0) or 0),
                    "leverage": int(float(row.get("leverage", 0) or 0)),
                    "margin_type": row.get("marginType"),
                }
                for row in raw_positions
                if float(row.get("positionAmt", 0) or 0) != 0
            ]

        snapshot["ok"] = True
        return snapshot

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = True,
    ) -> dict | list:
        params = dict(params) if params else {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params.setdefault("recvWindow", 5000)
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

    def _format_qty(self, qty: float) -> str:
        return f"{qty:.8f}".rstrip("0").rstrip(".")

    def _format_price(self, price: float) -> str:
        return f"{price:.8f}".rstrip("0").rstrip(".")

    def _map_status(self, status: str) -> OrderStatus:
        m = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.CANCELLED,
        }
        return m.get(status.upper(), OrderStatus.PENDING)

    def _prepare_symbol(self, symbol: str, leverage: int | None = None) -> None:
        if symbol in self._symbol_prepared:
            return
        try:
            self._request(
                "POST",
                "/fapi/v1/marginType",
                {"symbol": symbol, "marginType": self._margin_type},
            )
        except httpx.HTTPStatusError:
            # 이미 설정된 경우도 에러가 올 수 있어 경고만 남긴다.
            logger.debug("marginType already set or not changed: %s", symbol)

        lv = leverage if leverage is not None else self._default_leverage
        try:
            self._request(
                "POST",
                "/fapi/v1/leverage",
                {"symbol": symbol, "leverage": max(1, int(lv))},
            )
        except httpx.HTTPStatusError as e:
            logger.warning("leverage set failed for %s: %s", symbol, e)

        self._symbol_prepared.add(symbol)

    def place_order(self, order: Order) -> Order:
        self._prepare_symbol(order.symbol)
        params: dict = {
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": self._format_qty(order.quantity),
        }
        if self._position_side_mode == "HEDGE":
            params["positionSide"] = order.position_side
        if order.reduce_only:
            params["reduceOnly"] = "true"
        if order.close_position:
            params["closePosition"] = "true"
        if order.order_type == OrderType.LIMIT:
            if order.price is None:
                raise ValueError("LIMIT order requires price")
            params["price"] = self._format_price(order.price)
            params["timeInForce"] = "GTC"
        if order.order_type in (OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET):
            if order.stop_price is None:
                raise ValueError("STOP_MARKET/TAKE_PROFIT_MARKET requires stop_price")
            params["stopPrice"] = self._format_price(order.stop_price)
            params["workingType"] = "MARK_PRICE"

        try:
            data = self._request("POST", "/fapi/v1/order", params)
        except httpx.HTTPStatusError as e:
            logger.exception("Binance futures order failed: %s", e)
            order.status = OrderStatus.REJECTED
            return order

        order.order_id = str(data.get("orderId", ""))
        order.client_order_id = data.get("clientOrderId") or order.client_order_id
        order.status = self._map_status(data.get("status", ""))
        executed_qty = float(data.get("executedQty", 0) or 0)
        avg_price = float(data.get("avgPrice", 0) or 0)
        if executed_qty > 0:
            order.quantity = executed_qty
        if avg_price > 0:
            order.price = avg_price
        return order

    def place_exit_orders(
        self,
        symbol: str,
        position_side: str,
        quantity: float,
        take_profit_price: float | None,
        stop_loss_price: float | None,
    ) -> list[Order]:
        """
        Futures는 Spot OCO endpoint 대신 reduceOnly 조건부 주문 2개로 OCO 유사 보호를 구성한다.
        """
        if quantity <= 0:
            return []
        side = OrderSide.SELL if position_side == "LONG" else OrderSide.BUY
        out: list[Order] = []
        if take_profit_price is not None:
            tp_order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.TAKE_PROFIT_MARKET,
                quantity=quantity,
                stop_price=take_profit_price,
                reduce_only=True,
                position_side="LONG" if position_side == "LONG" else "SHORT",
            )
            out.append(self.place_order(tp_order))
        if stop_loss_price is not None:
            sl_order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.STOP_MARKET,
                quantity=quantity,
                stop_price=stop_loss_price,
                reduce_only=True,
                position_side="LONG" if position_side == "LONG" else "SHORT",
            )
            out.append(self.place_order(sl_order))
        return out

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            self._request("DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("Binance futures cancel failed: %s", e)
            return False

    def get_position(self, symbol: str) -> Position | None:
        try:
            data = self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
        except httpx.HTTPStatusError as e:
            logger.warning("Binance futures positionRisk failed: %s", e)
            return None
        if not isinstance(data, list) or not data:
            return None
        row = data[0]
        amt = float(row.get("positionAmt", 0) or 0)
        if amt == 0:
            return None
        side = "LONG" if amt > 0 else "SHORT"
        qty = abs(amt)
        entry_price = float(row.get("entryPrice", 0) or 0)
        return Position(
            symbol=symbol,
            quantity=qty,
            avg_entry_price=entry_price,
            side=side,
            updated_at=datetime.now(timezone.utc),
        )

    def get_all_positions(self) -> list[Position]:
        try:
            data = self._request("GET", "/fapi/v2/positionRisk")
        except httpx.HTTPStatusError as e:
            logger.warning("Binance futures positionRisk failed: %s", e)
            return []
        if not isinstance(data, list):
            return []
        out: list[Position] = []
        for row in data:
            amt = float(row.get("positionAmt", 0) or 0)
            if amt == 0:
                continue
            out.append(
                Position(
                    symbol=row.get("symbol", ""),
                    quantity=abs(amt),
                    avg_entry_price=float(row.get("entryPrice", 0) or 0),
                    side="LONG" if amt > 0 else "SHORT",
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return out

    def get_order(self, symbol: str, order_id: str) -> Order | None:
        try:
            data = self._request(
                "GET",
                "/fapi/v1/order",
                {"symbol": symbol, "orderId": order_id},
            )
        except httpx.HTTPStatusError:
            return None
        side = OrderSide(data.get("side", "BUY"))
        order_type = OrderType(data.get("type", "MARKET"))
        qty = float(data.get("executedQty", data.get("origQty", 0)) or 0)
        stop_price_raw = float(data.get("stopPrice", 0) or 0)
        return Order(
            symbol=data.get("symbol", symbol),
            side=side,
            order_type=order_type,
            quantity=qty,
            price=float(data.get("avgPrice", 0) or 0) or None,
            stop_price=stop_price_raw if stop_price_raw > 0 else None,
            status=self._map_status(data.get("status", "")),
            order_id=str(data.get("orderId", "")),
            client_order_id=data.get("clientOrderId"),
            reduce_only=bool(data.get("reduceOnly", False)),
            position_side=data.get("positionSide", "BOTH"),
        )

    def get_recent_trades(self, symbol: str, limit: int = 10) -> list[Trade]:
        try:
            data = self._request("GET", "/fapi/v1/userTrades", {"symbol": symbol, "limit": limit})
        except httpx.HTTPStatusError:
            return []
        if not isinstance(data, list):
            return []
        out: list[Trade] = []
        for t in data:
            qty = float(t.get("qty", 0) or 0)
            price = float(t.get("price", 0) or 0)
            out.append(
                Trade(
                    trade_id=str(t.get("id", "")),
                    order_id=str(t.get("orderId", "")),
                    symbol=symbol,
                    side=OrderSide.BUY if t.get("side") == "BUY" else OrderSide.SELL,
                    quantity=qty,
                    price=price,
                    commission=float(t.get("commission", 0) or 0),
                )
            )
        return out
