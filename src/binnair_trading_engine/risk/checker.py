"""
리스크 체커 인터페이스와 결과 객체를 정의한다.
주문 의도가 통과 가능한지 판단하는 공통 계약을 제공한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import Order, OrderIntent, Position, TradeContext


@dataclass
class RiskCheckResult:
    """리스크 체크 결과."""

    passed: bool
    reason: str = ""


class RiskChecker(ABC):
    """
    리스크 체크 인터페이스.
    현재 포지션, 최근 주문, 일손실 제한, 중복 주문 방지 체크 포함.
    """

    @abstractmethod
    def check(
        self,
        intent: "OrderIntent",
        ctx: "TradeContext",
        current_positions: list["Position"],
        recent_orders: list["Order"],
        daily_pnl: float,
    ) -> RiskCheckResult:
        """
        주문 전 리스크 검사.
        - current_positions: 현재 포지션 (max position 크기 등)
        - recent_orders: 최근 주문 (중복 주문 방지)
        - daily_pnl: 당일 손익 (일손실 제한)
        """
        ...
