"""
TorchPredictor 입력 feature vector 공급자를 정의한다.
현재는 테스트용 dummy vector provider를 제공한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import MarketSnapshot, TradeContext


class FeatureVectorProvider(ABC):
    """
    Feature 벡터 제공 인터페이스.
    Predictor가 모델 입력용 벡터를 요청. 실제 feature engineering은 별도 구현.
    """

    @abstractmethod
    def get_feature_vector(
        self,
        snapshot: "MarketSnapshot",
        ctx: "TradeContext",
    ) -> list[float]:
        """
        스냅샷과 컨텍스트로 feature 벡터 반환.
        feature_order_metadata 순서와 일치해야 함.
        """
        ...


class DummyFeatureVectorProvider(FeatureVectorProvider):
    """
    테스트/스켈레톤용 더미 제공자.
    실제 feature engineering 없이 placeholder 벡터 반환.
    """

    def __init__(self, dim: int = 8, fill: float = 0.0) -> None:
        self._dim = max(1, dim)
        self._fill = fill

    def get_feature_vector(
        self,
        snapshot: "MarketSnapshot",
        ctx: "TradeContext",
    ) -> list[float]:
        return [self._fill] * self._dim
