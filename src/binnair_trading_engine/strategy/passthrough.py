"""Pass-through 전략: predictor 출력을 그대로 OrderIntent로 전달."""

from binnair_trading_engine.domain.models import (
    OrderIntent,
    OrderSide,
    OrderType,
    Prediction,
    Signal,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.strategy.interface import Strategy


def _action_to_side(action: SignalAction) -> OrderSide | None:
    if action == SignalAction.BUY:
        return OrderSide.BUY
    if action == SignalAction.SELL:
        return OrderSide.SELL
    return None


class PassthroughStrategy(Strategy):
    """모델 예측을 최소 변형하여 주문 의도로 변환."""

    def __init__(self, tp_pct: float = 0.02, sl_pct: float = 0.01) -> None:
        self._tp_pct = max(0.0, tp_pct)
        self._sl_pct = max(0.0, sl_pct)

    def decide(
        self,
        signal: Signal,
        pred: Prediction,
        ctx: TradeContext,
    ) -> OrderIntent | None:
        side = _action_to_side(pred.action)
        if side is None:
            return None
        entry_price = pred.price_hint or signal.price_hint
        tp_price: float | None = None
        sl_price: float | None = None
        if entry_price is not None:
            if side == OrderSide.BUY:
                tp_price = entry_price * (1.0 + self._tp_pct)
                sl_price = entry_price * (1.0 - self._sl_pct)
            else:
                tp_price = entry_price * (1.0 - self._tp_pct)
                sl_price = entry_price * (1.0 + self._sl_pct)

        return OrderIntent(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=1.0,  # TODO: 전략별 수량 계산
            price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            position_side="LONG" if side == OrderSide.BUY else "SHORT",
        )
