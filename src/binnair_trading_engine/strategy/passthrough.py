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

    def decide(
        self,
        signal: Signal,
        pred: Prediction,
        ctx: TradeContext,
    ) -> OrderIntent | None:
        side = _action_to_side(pred.action)
        if side is None:
            return None
        return OrderIntent(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=1.0,  # TODO: 전략별 수량 계산
            price=pred.price_hint,
        )
