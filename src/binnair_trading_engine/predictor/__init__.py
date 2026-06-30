"""
예측기 패키지와 Predictor factory를 제공한다.
설정에 따라 TimesFM 예측기를 생성하고, 검증용 Dummy/RuleBased 예측기를 노출한다.
"""

from __future__ import annotations

import logging

from binnair_trading_engine.predictor.dummy import DummyPredictor
from binnair_trading_engine.predictor.interface import Predictor
from binnair_trading_engine.predictor.rule_based import RuleBasedPredictor
from binnair_trading_engine.predictor.timesfm_predictor import TimesFMPredictor

logger = logging.getLogger(__name__)

__all__ = [
    "Predictor",
    "DummyPredictor",
    "RuleBasedPredictor",
    "TimesFMPredictor",
    "create_predictor",
]


def create_predictor(config, price_history_provider=None) -> Predictor:
    """설정에 따라 Predictor 생성 (운영 기본값은 timesfm)."""
    from binnair_trading_engine.config.settings import EngineConfig

    cfg: EngineConfig = config
    if cfg.predictor_type == "rule_based":
        return RuleBasedPredictor()
    if cfg.predictor_type == "timesfm":
        from binnair_trading_engine.config.settings import PredictorTimesFMConfig

        return TimesFMPredictor(
            config=cfg.predictor_timesfm_config or PredictorTimesFMConfig(),
            price_history_provider=price_history_provider,
        )
    from binnair_trading_engine.config.settings import PredictorTimesFMConfig

    logger.warning(
        "Unknown or incomplete predictor_type=%s, falling back to TimesFM",
        cfg.predictor_type,
    )
    return TimesFMPredictor(
        config=cfg.predictor_timesfm_config or PredictorTimesFMConfig(),
        price_history_provider=price_history_provider,
    )
