"""
Rule-based 예측기 스켈레톤.
간단한 규칙(가격 임계값 등) 기반 BUY/SELL/HOLD.
"""
from __future__ import annotations

from binnair_trading_engine.domain.models import (
    MarketSnapshot,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.predictor.interface import Predictor


class RuleBasedPredictor(Predictor):
    """
    규칙 기반 예측기.
    TODO: 실제 규칙 로직 (예: price > threshold -> BUY).
    """

    def __init__(
        self,
        buy_threshold: float | None = None,
        sell_threshold: float | None = None,
    ) -> None:
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def predict(
        self,
        snapshot: MarketSnapshot,
        ctx: TradeContext,
    ) -> Prediction | None:
        # TODO: 규칙 적용. 현재는 HOLD.
        action = SignalAction.HOLD
        if self._buy_threshold is not None and snapshot.price < self._buy_threshold:
            action = SignalAction.BUY
        elif self._sell_threshold is not None and snapshot.price > self._sell_threshold:
            action = SignalAction.SELL
        return Prediction(
            action=action,
            confidence=0.0,
            price_hint=snapshot.price,
            model_version=ctx.model_version,
            feature_set_version=ctx.feature_set_version,
        )
