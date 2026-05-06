"""Strategy - 시그널 해석 및 주문 의사결정."""

from binnair_trading_engine.strategy.exit_manager import ExitManager
from binnair_trading_engine.strategy.interface import Strategy
from binnair_trading_engine.strategy.passthrough import PassthroughStrategy

__all__ = ["Strategy", "PassthroughStrategy", "ExitManager", "create_strategy"]


def create_strategy(config) -> Strategy:
    """설정에 따라 Strategy 생성."""
    rules = getattr(config, "trade_rules", None)
    if rules is None:
        return PassthroughStrategy()
    return PassthroughStrategy(tp_pct=rules.tp_pct, sl_pct=rules.sl_pct)
