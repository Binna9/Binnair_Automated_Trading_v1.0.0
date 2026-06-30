"""
전략 공통 인터페이스를 정의한다.
Signal과 Prediction을 주문 의도 OrderIntent로 변환하는 계약을 제공한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import OrderIntent, Prediction, Signal, TradeContext


class Strategy(ABC):
    """시그널 + 예측 -> OrderIntent 의사결정."""

    @abstractmethod
    def decide(
        self,
        signal: "Signal",
        pred: "Prediction",
        ctx: "TradeContext",
    ) -> "OrderIntent | None":
        """주문 불필요 시 None."""
        ...
