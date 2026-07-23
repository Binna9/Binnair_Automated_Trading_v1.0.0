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
    Soft signal 공급자 (inference).

    MarketSnapshot → BUY/SELL/HOLD 후보. 최종 진입 권한이 아니며,
    consecutive policy(soft) + RiskChecker(hard)를 통과해야 실행된다.
    역할: docs/RISK_FIRST_DIRECTION.md
    """

    @abstractmethod
    def predict(
        self,
        snapshot: "MarketSnapshot",
        ctx: "TradeContext",
        *,
        for_exit: bool = False,
    ) -> Prediction | None:
        """마켓 스냅샷으로 soft 예측 (buy/sell/hold). for_exit=True면 청산 threshold."""
        ...
