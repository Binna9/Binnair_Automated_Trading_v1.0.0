"""FinCastPredictor factory·HOLD fallback 테스트 (모델 로드 없음)."""

from __future__ import annotations

from types import SimpleNamespace

from binnair_trading_engine.config.settings import PredictorFinCastConfig
from binnair_trading_engine.domain.models import MarketSnapshot, TradeContext
from binnair_trading_engine.predictor import create_predictor
from binnair_trading_engine.predictor.fincast_predictor import FinCastPredictor


def _ctx() -> TradeContext:
    return TradeContext(
        run_id="test",
        strategy_id="s",
        model_version="v",
        feature_set_version="f",
        symbol="BTCUSDT",
    )


def test_fincast_hold_when_checkpoint_missing() -> None:
    cfg = PredictorFinCastConfig(
        checkpoint_path="/nonexistent/fincast.pth",
        predict_on_candle_close=False,
        min_context=1,
        safety_margin=0.0001,
    )
    predictor = FinCastPredictor(config=cfg, price_history_provider=None)
    assert predictor._model is None
    out = predictor.predict(MarketSnapshot(symbol="BTCUSDT", price=100.0), _ctx())
    assert out is not None
    assert out.hold_reason == "model_unloaded"


def test_create_predictor_fincast_branch() -> None:
    engine_cfg = SimpleNamespace(
        predictor_type="fincast",
        predictor_fincast_config=PredictorFinCastConfig(
            checkpoint_path="",
            predict_on_candle_close=False,
            min_context=1,
        ),
        predictor_timesfm_config=None,
    )
    pred = create_predictor(engine_cfg, price_history_provider=None)
    assert isinstance(pred, FinCastPredictor)
    out = pred.predict(MarketSnapshot(symbol="BTCUSDT", price=1.0), _ctx())
    assert out is not None
    assert out.hold_reason == "model_unloaded"


def test_fincast_set_thresholds() -> None:
    cfg = PredictorFinCastConfig(checkpoint_path="", safety_margin=0.0001)
    pred = FinCastPredictor(config=cfg, price_history_provider=None)
    pred.set_thresholds(0.002, 0.001)
    assert pred.get_threshold() == 0.002
    assert pred.get_exit_threshold() == 0.001
