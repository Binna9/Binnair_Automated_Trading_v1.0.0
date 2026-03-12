"""예측 모듈 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from binnair_trading_engine.domain.models import Prediction

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import MarketSnapshot, TradeContext


class Predictor(ABC):
    """
    추론 인터페이스 (inference/model 분리).
    market snapshot(tick) -> signal evaluation (buy/sell/hold).
    """

    @abstractmethod
    def predict(
        self, snapshot: "MarketSnapshot", ctx: "TradeContext"
    ) -> Prediction | None:
        """마켓 스냅샷으로 예측 결과 반환 (buy/sell/hold)."""
        ...
