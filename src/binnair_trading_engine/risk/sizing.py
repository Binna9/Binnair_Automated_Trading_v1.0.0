"""
지갑 잔고 기반 포지션 사이징 정책을 구현한다.
허용 손실, 손절 거리, 최대 포지션 비율로 주문 수량을 계산한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from binnair_trading_engine.config.settings import SizingConfig


@dataclass(frozen=True)
class SizingResult:
    """포지션 사이징 결과."""

    quantity: float
    notional: float
    equity: float
    reason: str = "ok"

    @property
    def is_valid(self) -> bool:
        return self.quantity > 0 and self.notional > 0


class PercentEquitySizingPolicy:
    """
    지갑 잔고와 손절 거리로 주문 수량을 계산한다.

    계산 순서:
    1. 지갑 잔고 * risk_per_trade_pct = 1회 허용 손실
    2. 허용 손실 / 손절 거리 = 이론상 주문 명목 금액
    3. 지갑 잔고 * max_position_notional_pct로 최대 주문 금액 제한
    4. 최종 주문 금액 / 진입가 = 주문 수량
    """

    def __init__(self, config: SizingConfig) -> None:
        self._config = config

    def calculate(
        self,
        *,
        equity: float,
        entry_price: float | None,
        stop_loss_price: float | None,
    ) -> SizingResult:
        if equity <= 0:
            return SizingResult(0.0, 0.0, equity, "equity_not_available")
        if entry_price is None or entry_price <= 0:
            return SizingResult(0.0, 0.0, equity, "entry_price_not_available")

        stop_distance_pct = self._stop_distance_pct(entry_price, stop_loss_price)
        if stop_distance_pct <= 0:
            return SizingResult(0.0, 0.0, equity, "stop_loss_not_available")

        risk_budget = equity * self._config.risk_per_trade_pct
        risk_based_notional = risk_budget / stop_distance_pct
        max_notional = equity * self._config.max_position_notional_pct
        leverage_cap_notional = equity * max(1, self._config.max_leverage)
        notional = min(risk_based_notional, max_notional, leverage_cap_notional)

        if notional < self._config.min_order_notional_usdt:
            return SizingResult(0.0, notional, equity, "below_min_order_notional")

        quantity = notional / entry_price
        # 명목 한도 초과 방지: qty×price가 max_notional을 넘지 않도록 내림.
        if quantity * entry_price > max_notional:
            quantity = math.floor((max_notional / entry_price) * 1e8) / 1e8
            notional = quantity * entry_price

        if notional < self._config.min_order_notional_usdt:
            return SizingResult(0.0, notional, equity, "below_min_order_notional")

        return SizingResult(quantity=quantity, notional=notional, equity=equity)

    def _stop_distance_pct(
        self,
        entry_price: float,
        stop_loss_price: float | None,
    ) -> float:
        if stop_loss_price is None:
            return 0.0
        return abs(entry_price - stop_loss_price) / entry_price
