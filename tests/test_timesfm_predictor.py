"""TimesFMPredictor threshold·hold_reason 테스트 (모델 로드 없음)."""

from __future__ import annotations

from datetime import datetime, timezone

from binnair_trading_engine.config.settings import PredictorTimesFMConfig
from binnair_trading_engine.domain.models import MarketSnapshot, SignalAction, TradeContext
from binnair_trading_engine.predictor.timesfm_predictor import TimesFMPredictor


def _ctx() -> TradeContext:
    return TradeContext(
        run_id="test",
        strategy_id="s",
        model_version="v",
        feature_set_version="f",
        symbol="XRPUSDT",
    )


def test_to_action_uses_entry_and_exit_thresholds() -> None:
    cfg = PredictorTimesFMConfig(timeframe="1m", safety_margin=0.0001)
    pred = TimesFMPredictor(config=cfg, price_history_provider=None)
    pred.set_thresholds(0.001, 0.0005)

    assert pred._to_action(0.0011, pred.get_threshold()) == SignalAction.BUY
    assert pred._to_action(-0.0006, pred.get_exit_threshold()) == SignalAction.SELL
    assert pred._to_action(0.0003, pred.get_threshold()) == SignalAction.HOLD


def test_hold_awaiting_candle_close() -> None:
    cfg = PredictorTimesFMConfig(
        timeframe="5m",
        predict_on_candle_close=True,
        min_context=2,
        safety_margin=0.0001,
    )

    class StubProvider:
        def get_recent_prices(self, symbol: str, timeframe: str, limit: int) -> list[float]:
            return [1.0, 1.01, 1.02, 1.03]

        def get_latest_candle_open_time(self, symbol: str, timeframe: str) -> datetime:
            return datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)

    predictor = TimesFMPredictor(config=cfg, price_history_provider=StubProvider())
    predictor._model = object()  # min_context 통과용 stub
    predictor._last_infer_candle_open_time["XRPUSDT"] = datetime(
        2026, 7, 10, 12, 0, tzinfo=timezone.utc
    )

    snap = MarketSnapshot(symbol="XRPUSDT", price=1.04)
    out = predictor.predict(snap, _ctx(), for_exit=False)
    assert out is not None
    assert out.action == SignalAction.HOLD
    assert out.hold_reason == "awaiting_candle_close"


def test_hold_model_unloaded() -> None:
    cfg = PredictorTimesFMConfig(
        predict_on_candle_close=False,
        min_context=1,
        safety_margin=0.0001,
    )
    predictor = TimesFMPredictor(config=cfg, price_history_provider=None)
    predictor._model = None
    snap = MarketSnapshot(symbol="XRPUSDT", price=1.0)
    out = predictor.predict(snap, _ctx())
    assert out is not None
    assert out.hold_reason == "model_unloaded"
