"""
보유 포지션의 TP/SL 청산 조건을 판단한다.
가격이 목표가 또는 손절가에 도달하면 reduce-only 청산 의도를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from binnair_trading_engine.domain.models import (
    OrderIntent,
    OrderSide,
    OrderType,
)

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import MarketSnapshot, Position


EXIT_TAKE_PROFIT = "TAKE_PROFIT"
EXIT_STOP_LOSS = "STOP_LOSS"


@dataclass
class ExitIntent:
    """청산 의도. OrderIntent + reason(TAKE_PROFIT|STOP_LOSS)."""

    intent: OrderIntent
    reason: str  # EXIT_TAKE_PROFIT | EXIT_STOP_LOSS


class ExitManager:
    """
    TP/SL 기반 청산 의사결정.
    current_price와 포지션 tp_price, sl_price 비교만 수행.
    """

    def check_exit(
        self, position: "Position", snapshot: "MarketSnapshot"
    ) -> ExitIntent | None:
        """
        포지션 + 현재가 기준 TP/SL 도달 여부 판단.
        LONG: price >= tp_price → TAKE_PROFIT, price <= sl_price → STOP_LOSS.
        SHORT: price <= tp_price → TAKE_PROFIT, price >= sl_price → STOP_LOSS.
        도달 시 청산 OrderIntent 생성. 아니면 None.
        """
        price = snapshot.price
        symbol = snapshot.symbol

        if not position.is_open():
            return None

        if position.side == "SHORT":
            tp_hit = position.tp_price is not None and price <= position.tp_price
            sl_hit = position.sl_price is not None and price >= position.sl_price
            close_side = OrderSide.BUY
        else:
            tp_hit = position.tp_price is not None and price >= position.tp_price
            sl_hit = position.sl_price is not None and price <= position.sl_price
            close_side = OrderSide.SELL

        if tp_hit:
            reason = EXIT_TAKE_PROFIT
        elif sl_hit:
            reason = EXIT_STOP_LOSS
        else:
            return None

        intent = OrderIntent(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=position.quantity,
            price=None,
            reduce_only=True,
            position_side="SHORT" if position.side == "SHORT" else "LONG",
        )
        return ExitIntent(intent=intent, reason=reason)
