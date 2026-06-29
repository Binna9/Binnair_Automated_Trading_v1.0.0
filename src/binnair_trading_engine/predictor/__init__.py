"""예측/추론 모듈."""

from __future__ import annotations

import logging

from binnair_trading_engine.predictor.dummy import DummyPredictor
from binnair_trading_engine.predictor.interface import Predictor
from binnair_trading_engine.predictor.rule_based import RuleBasedPredictor
from binnair_trading_engine.predictor.timesfm_predictor import TimesFMPredictor
from binnair_trading_engine.predictor.torch_predictor import TorchPredictor

logger = logging.getLogger(__name__)

__all__ = [
    "Predictor",
    "DummyPredictor",
    "RuleBasedPredictor",
    "TimesFMPredictor",
    "TorchPredictor",
    "create_predictor",
]


def create_predictor(config) -> Predictor:
    """설정에 따라 Predictor 생성 (rule_based, torch, timesfm 지원)."""
    from binnair_trading_engine.config.settings import EngineConfig
    from binnair_trading_engine.predictor.artifact import ModelArtifactMetadata
    from binnair_trading_engine.predictor.feature_provider import DummyFeatureVectorProvider

    cfg: EngineConfig = config
    if cfg.predictor_type == "rule_based":
        return RuleBasedPredictor()
    if cfg.predictor_type == "timesfm":
        from binnair_trading_engine.config.settings import PredictorTimesFMConfig

        return TimesFMPredictor(
            config=cfg.predictor_timesfm_config or PredictorTimesFMConfig()
        )
    if cfg.predictor_type == "torch" and cfg.predictor_config:
        artifact = ModelArtifactMetadata(
            model_path=cfg.predictor_config.model_path,
            scaler_path=cfg.predictor_config.scaler_path or None,
            feature_order_path=cfg.predictor_config.feature_order_path or None,
            model_version=cfg.predictor_config.model_version,
            feature_set_version=cfg.predictor_config.feature_set_version,
            scaler_version=cfg.predictor_config.scaler_version,
        )
        provider = DummyFeatureVectorProvider(dim=8, fill=0.0)
        return TorchPredictor(artifact=artifact, feature_provider=provider)
    from binnair_trading_engine.config.settings import PredictorTimesFMConfig

    logger.warning(
        "Unknown or incomplete predictor_type=%s, falling back to TimesFM",
        cfg.predictor_type,
    )
    return TimesFMPredictor(
        config=cfg.predictor_timesfm_config or PredictorTimesFMConfig()
    )
