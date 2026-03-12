"""종이거래(Paper Trading) 거래소 어댑터."""

import uuid
from datetime import datetime

from binnair_trading_engine.domain.models import (
    Order,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
)
from binnair_trading_engine.exchange.interface import ExchangeAdapter


class PaperExchangeAdapter(ExchangeAdapter):
    """실제 API 없이 메모리 내 시뮬레이션."""

    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}

    def place_order(self, order: Order) -> Order:
        """종이거래: Market 주문 즉시 체결 시뮬레이션."""
        order.order_id = order.order_id or str(uuid.uuid4())
        order.client_order_id = order.client_order_id or str(uuid.uuid4())
        order.status = OrderStatus.SUBMITTED

        if order.order_type.value == "MARKET":
            order.status = OrderStatus.FILLED
            self._update_position(order)
            self._orders[order.order_id] = order

        return order

    def _update_position(self, order: Order) -> None:
        pos = self._positions.get(order.symbol)
        qty = order.quantity if order.side == OrderSide.BUY else -order.quantity
        price = order.price or 0.0

        if pos is None:
            if qty > 0:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=qty,
                    avg_entry_price=price,
                    updated_at=datetime.utcnow(),
                )
        else:
            new_qty = pos.quantity + qty
            if new_qty == 0:
                del self._positions[order.symbol]
            else:
                new_avg = (
                    (pos.avg_entry_price * pos.quantity + price * qty) / new_qty
                    if new_qty != 0
                    else pos.avg_entry_price
                )
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=new_qty,
                    avg_entry_price=new_avg,
                    updated_at=datetime.utcnow(),
                )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        o = self._orders.get(order_id)
        if o and o.symbol == symbol and o.status == OrderStatus.SUBMITTED:
            o.status = OrderStatus.CANCELLED
            return True
        return False

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_order(self, symbol: str, order_id: str) -> Order | None:
        o = self._orders.get(order_id)
        return o if o and o.symbol == symbol else None

    def get_recent_trades(self, symbol: str, limit: int = 10) -> list[Trade]:
        return []

    def submit_order(
        self, intent: OrderIntent, execution_price: float | None = None
    ) -> Order | None:
        """OrderIntent를 Order로 변환 후 place_order 호출."""
        price = execution_price if execution_price is not None else intent.price
        order = Order(
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            price=price,
        )
        return self.place_order(order)
