#!/usr/bin/env python3
"""
샘플 추론 플로우: RuleBasedPredictor, TorchPredictor, TimesFMPredictor 각각으로 inference 실행.
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.domain.models import (
    EngineContext,
    MarketSnapshot,
    TradeContext,
)
from binnair_trading_engine.predictor import (
    RuleBasedPredictor,
    TimesFMPredictor,
    TorchPredictor,
)
from binnair_trading_engine.predictor.artifact import ModelArtifactMetadata
from binnair_trading_engine.predictor.feature_provider import DummyFeatureVectorProvider
from binnair_trading_engine.config.settings import PredictorTimesFMConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)

ENGINE_CTX = EngineContext(
    version="1.0.0",
    run_id="sample_inference_run",
    strategy_id="sample_strategy",
    model_version="v1",
    feature_set_version="v1",
)

SNAPSHOT = MarketSnapshot(
    symbol="BTCUSDT",
    price=50000.0,
    timestamp=datetime.now(timezone.utc),
    run_id=ENGINE_CTX.run_id,
    correlation_id=str(uuid.uuid4()),
)


def run_inference(predictor_name: str, predictor) -> None:
    """단일 predictor로 추론 실행."""
    ctx = TradeContext.from_snapshot(SNAPSHOT, ENGINE_CTX)
    pred = predictor.predict(SNAPSHOT, ctx)
    if pred:
        score_str = f", score={pred.score}" if pred.score is not None else ""
        prob_str = f", probability={pred.probability}" if pred.probability else ""
        logging.info(
            "%s -> action=%s, confidence=%.4f%s%s",
            predictor_name,
            pred.action.value,
            pred.confidence,
            score_str,
            prob_str,
        )
    else:
        logging.info("%s -> None", predictor_name)


def main() -> int:
    # 1. RuleBasedPredictor (가격 임계값)
    logging.info("=== RuleBasedPredictor ===")
    rule = RuleBasedPredictor(buy_threshold=60000.0, sell_threshold=40000.0)
    run_inference("RuleBasedPredictor", rule)

    # 2. TorchPredictor (artifact 없으면 HOLD fallback)
    logging.info("=== TorchPredictor (fallback HOLD) ===")
    artifact = ModelArtifactMetadata(
        model_path="./models/nonexistent.pt",
        scaler_path=None,
        feature_order_path=None,
        model_version="v1",
        feature_set_version="v1",
        scaler_version="v1",
    )
    provider = DummyFeatureVectorProvider(dim=8, fill=0.0)
    torch_pred = TorchPredictor(artifact=artifact, feature_provider=provider)
    run_inference("TorchPredictor", torch_pred)

    # 3. TimesFMPredictor (히스토리 부족 시 HOLD)
    logging.info("=== TimesFMPredictor (warmup HOLD) ===")
    timesfm_pred = TimesFMPredictor(
        PredictorTimesFMConfig(context_length=8, min_context=4, horizon=1)
    )
    run_inference("TimesFMPredictor", timesfm_pred)

    return 0


if __name__ == "__main__":
    sys.exit(main())
