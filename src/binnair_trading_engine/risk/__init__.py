"""
리스크 관리 패키지와 RiskChecker factory를 제공한다.
설정과 거래소 잔고를 바탕으로 기본 리스크 체커를 생성한다.
"""

from .checker import RiskChecker, RiskCheckResult
from .default import DefaultRiskChecker

__all__ = ["RiskChecker", "RiskCheckResult", "DefaultRiskChecker", "create_risk_checker"]


def create_risk_checker(config, exchange=None) -> RiskChecker:
    """설정에 따라 RiskChecker 생성."""
    risk = getattr(config, "risk", None)
    sizing = getattr(config, "sizing", None)
    quote_asset = getattr(sizing, "quote_asset", "USDT")
    fallback_equity = float(getattr(sizing, "fallback_equity_usdt", 0.0))

    def _equity_provider() -> float:
        if exchange is None:
            return fallback_equity
        equity = exchange.get_available_balance(quote_asset)
        return equity if equity > 0 else fallback_equity

    return DefaultRiskChecker(
        max_position_notional_pct=getattr(risk, "max_position_notional_pct", 0.20),
        daily_loss_limit_pct=getattr(risk, "daily_loss_limit_pct", 0.03),
        duplicate_window_seconds=getattr(
            risk,
            "duplicate_order_window_seconds",
            180,
        ),
        equity_provider=_equity_provider,
    )
