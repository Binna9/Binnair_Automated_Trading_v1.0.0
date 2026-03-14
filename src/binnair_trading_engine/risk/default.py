"""기본 리스크 체커 구현."""

from datetime import datetime, timedelta, timezone

from binnair_trading_engine.domain.models import Order, OrderIntent, OrderSide, Position, TradeContext
from binnair_trading_engine.risk.checker import RiskCheckResult, RiskChecker
from binnair_trading_engine.risk.config import (
    DEFAULT_DAILY_LOSS_LIMIT,
    DEFAULT_DUPLICATE_ORDER_WINDOW_SECONDS,
    DEFAULT_MAX_POSITION_QTY,
)


class DefaultRiskChecker(RiskChecker):
    """
    기본 리스크 체커.
    - 현재 포지션 크기 제한
    - 일손실 제한
    - 중복 주문 방지
    """

    def __init__(
        self,
        max_position_qty: float = DEFAULT_MAX_POSITION_QTY,
        daily_loss_limit: float = DEFAULT_DAILY_LOSS_LIMIT,
        duplicate_window_seconds: int = DEFAULT_DUPLICATE_ORDER_WINDOW_SECONDS,
    ) -> None:
        self._max_position_qty = max_position_qty
        self._daily_loss_limit = daily_loss_limit
        self._duplicate_window_seconds = duplicate_window_seconds

    def check(
        self,
        intent: OrderIntent,
        ctx: TradeContext,
        current_positions: list[Position],
        recent_orders: list[Order],
        daily_pnl: float,
    ) -> RiskCheckResult:
        """포지션/일손실/중복 주문 검사."""
        # 1. 일손실 제한 (daily_loss_limit 은 음수, 손실이 한도 초과 시 거부)
        if daily_pnl < self._daily_loss_limit:
            return RiskCheckResult(
                passed=False,
                reason=f"daily_loss_limit: pnl={daily_pnl:.2f} < {self._daily_loss_limit}",
            )

        # 2. 현재 포지션 크기 (해당 심볼)
        pos_qty = 0.0
        for p in current_positions:
            if p.symbol == intent.symbol:
                pos_qty = p.quantity
                break

        new_qty = pos_qty + (intent.quantity if intent.side == OrderSide.BUY else -intent.quantity)
        if abs(new_qty) > self._max_position_qty:
            return RiskCheckResult(
                passed=False,
                reason=f"max_position: new_qty={new_qty:.2f} > {self._max_position_qty}",
            )

        # 3. 중복 주문 방지
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self._duplicate_window_seconds
        )
        for o in recent_orders:
            if o.symbol == intent.symbol and o.side == intent.side and o.created_at >= cutoff:
                return RiskCheckResult(
                    passed=False,
                    reason=f"duplicate_order: same {intent.side.value} within {self._duplicate_window_seconds}s",
                )

        return RiskCheckResult(passed=True, reason="ok")
