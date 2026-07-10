"""
고정 action을 반환하는 테스트용 예측기다.
엔진 시나리오와 persistence 검증에서 결정적 시그널을 만들 때 사용한다.
"""

from binnair_trading_engine.domain.models import (
    MarketSnapshot,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.predictor.interface import Predictor


class DummyPredictor(Predictor):
    """
    기본값 HOLD, action 오버라이드 가능한 더미 예측기.
    테스트에서 force_action으로 BUY/SELL 고정 가능.
    """

    def __init__(self, force_action: SignalAction | None = None) -> None:
        self._force_action = force_action

    def predict(
        self,
        snapshot: MarketSnapshot,
        ctx: TradeContext,
        *,
        for_exit: bool = False,
    ) -> Prediction | None:
        action = self._force_action or SignalAction.HOLD
        return Prediction(
            action=action,
            confidence=0.0,
            price_hint=snapshot.price,
        )
