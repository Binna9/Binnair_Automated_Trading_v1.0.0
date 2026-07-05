"""Autopilot — TimesFM threshold·TP/SL·신호 정책 자동 조정."""

from binnair_trading_engine.autopilot.models import AutopilotConfig, AutopilotState

__all__ = ["AutopilotController", "AutopilotConfig", "AutopilotState"]


def __getattr__(name: str):
    if name == "AutopilotController":
        from binnair_trading_engine.autopilot.controller import AutopilotController

        return AutopilotController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
