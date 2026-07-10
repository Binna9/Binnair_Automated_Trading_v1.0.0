"""
예측기 공통 인터페이스를 정의한다.
MarketSnapshot과 TradeContext를 받아 Prediction을 반환하는 계약을 제공한다.
"""

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
        self,
        snapshot: "MarketSnapshot",
        ctx: "TradeContext",
        *,
        for_exit: bool = False,
    ) -> Prediction | None:
        """마켓 스냅샷으로 예측 결과 반환 (buy/sell/hold). for_exit=True면 청산 threshold."""
        ...
