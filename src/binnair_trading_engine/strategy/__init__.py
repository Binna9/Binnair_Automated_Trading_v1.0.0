"""Strategy - 시그널 해석 및 주문 의사결정."""

from binnair_trading_engine.strategy.interface import Strategy
from binnair_trading_engine.strategy.passthrough import PassthroughStrategy

__all__ = ["Strategy", "PassthroughStrategy", "create_strategy"]


def create_strategy(config) -> Strategy:
    """설정에 따라 Strategy 생성."""
    return PassthroughStrategy()
