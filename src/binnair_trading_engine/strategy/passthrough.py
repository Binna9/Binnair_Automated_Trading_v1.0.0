"""
모델 시그널을 최소 변형해 주문 의도로 바꾸는 기본 전략이다.
TP/SL 가격과 잔고 기반 주문 수량을 계산한다.
"""

from binnair_trading_engine.domain.models import (
    OrderIntent,
    OrderSide,
    OrderType,
    Prediction,
    Signal,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.exchange import ExchangeAdapter
from binnair_trading_engine.risk.sizing import PercentEquitySizingPolicy
from binnair_trading_engine.strategy.interface import Strategy


def _action_to_side(action: SignalAction) -> OrderSide | None:
    if action == SignalAction.BUY:
        return OrderSide.BUY
    if action == SignalAction.SELL:
        return OrderSide.SELL
    return None


class PassthroughStrategy(Strategy):
    """모델 예측을 최소 변형하여 주문 의도로 변환."""

    def __init__(
        self,
        tp_pct: float = 0.02,
        sl_pct: float = 0.01,
        sizing_policy: PercentEquitySizingPolicy | None = None,
        exchange: ExchangeAdapter | None = None,
        quote_asset: str = "USDT",
        fallback_equity_usdt: float = 0.0,
    ) -> None:
        self._tp_pct = max(0.0, tp_pct)
        self._sl_pct = max(0.0, sl_pct)
        self._sizing_policy = sizing_policy
        self._exchange = exchange
        self._quote_asset = quote_asset
        self._fallback_equity_usdt = max(0.0, fallback_equity_usdt)
        self._position_scale = 1.0

    def set_dynamic_exit(
        self,
        *,
        tp_pct: float,
        sl_pct: float,
        position_scale: float = 1.0,
    ) -> None:
        """Autopilot — ATR 기반 TP/SL % 및 포지션 축소."""
        self._tp_pct = max(0.0, tp_pct)
        self._sl_pct = max(0.0, sl_pct)
        self._position_scale = max(0.1, min(1.0, position_scale))

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
                if self._tp_pct > 0:
                    tp_price = entry_price * (1.0 + self._tp_pct)
                if self._sl_pct > 0:
                    sl_price = entry_price * (1.0 - self._sl_pct)
            else:
                if self._tp_pct > 0:
                    tp_price = entry_price * (1.0 - self._tp_pct)
                if self._sl_pct > 0:
                    sl_price = entry_price * (1.0 + self._sl_pct)

        quantity = self._calculate_quantity(entry_price, sl_price)
        if quantity <= 0:
            return None

        return OrderIntent(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            position_side="LONG" if side == OrderSide.BUY else "SHORT",
        )

    def _calculate_quantity(
        self,
        entry_price: float | None,
        stop_loss_price: float | None,
    ) -> float:
        if self._sizing_policy is None:
            return 1.0

        equity = self._get_equity()
        result = self._sizing_policy.calculate(
            equity=equity,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
        )
        if not result.is_valid:
            return 0.0
        return result.quantity * self._position_scale

    def _get_equity(self) -> float:
        if self._exchange is None:
            return self._fallback_equity_usdt

        equity = self._exchange.get_available_balance(self._quote_asset)
        if equity > 0:
            return equity
        return self._fallback_equity_usdt
