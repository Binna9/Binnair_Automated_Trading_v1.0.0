"""
전략 패키지와 Strategy factory를 제공한다.
설정과 sizing policy를 조합해 기본 PassthroughStrategy를 생성한다.
"""

from binnair_trading_engine.strategy.exit_manager import ExitManager
from binnair_trading_engine.strategy.interface import Strategy
from binnair_trading_engine.strategy.passthrough import PassthroughStrategy

__all__ = ["Strategy", "PassthroughStrategy", "ExitManager", "create_strategy"]


def create_strategy(config, exchange=None) -> Strategy:
    """설정에 따라 Strategy 생성."""
    from binnair_trading_engine.risk.sizing import PercentEquitySizingPolicy

    rules = getattr(config, "trade_rules", None)
    sizing = getattr(config, "sizing", None)
    sizing_policy = PercentEquitySizingPolicy(sizing) if sizing is not None else None
    if rules is None:
        return PassthroughStrategy(
            sizing_policy=sizing_policy,
            exchange=exchange,
            quote_asset=getattr(sizing, "quote_asset", "USDT"),
            fallback_equity_usdt=getattr(sizing, "fallback_equity_usdt", 0.0),
        )
    return PassthroughStrategy(
        tp_pct=rules.tp_pct,
        sl_pct=rules.sl_pct,
        sizing_policy=sizing_policy,
        exchange=exchange,
        quote_asset=getattr(sizing, "quote_asset", "USDT"),
        fallback_equity_usdt=getattr(sizing, "fallback_equity_usdt", 0.0),
    )
