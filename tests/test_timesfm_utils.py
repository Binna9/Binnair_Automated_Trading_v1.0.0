"""TimesFM threshold·timeframe 유틸 테스트."""

from __future__ import annotations

from binnair_trading_engine.config.settings import PredictorTimesFMConfig
from binnair_trading_engine.predictor.timesfm_utils import (
    compute_entry_threshold,
    compute_exit_threshold,
    compute_fee_floor,
    timeframe_to_minutes,
    timeframe_to_seconds,
)


def test_timeframe_to_minutes() -> None:
    assert timeframe_to_minutes("1m") == 1.0
    assert timeframe_to_minutes("5m") == 5.0
    assert timeframe_to_minutes("1h") == 60.0
    assert timeframe_to_seconds("5m") == 300


def test_fee_floor() -> None:
    floor = compute_fee_floor(fee_rate=0.0004, slippage_rate=0.0005, safety_margin=0.0001)
    assert abs(floor - 0.0014) < 1e-9


def test_entry_threshold_scales_down_for_5m() -> None:
    cfg_1m = PredictorTimesFMConfig(timeframe="1m", safety_margin=0.0001)
    cfg_5m = PredictorTimesFMConfig(timeframe="5m", safety_margin=0.0001)
    t1 = compute_entry_threshold(cfg_1m)
    t5 = compute_entry_threshold(cfg_5m)
    assert t5 < t1
    assert t5 >= compute_fee_floor(
        fee_rate=cfg_5m.fee_rate,
        slippage_rate=cfg_5m.slippage_rate,
        safety_margin=cfg_5m.safety_margin,
    ) * cfg_5m.min_threshold_fee_ratio


def test_signal_threshold_override() -> None:
    cfg = PredictorTimesFMConfig(timeframe="5m", signal_threshold=0.0008)
    assert compute_entry_threshold(cfg) == 0.0008


def test_exit_threshold_mult() -> None:
    cfg = PredictorTimesFMConfig(timeframe="1m", safety_margin=0.0001)
    entry = compute_entry_threshold(cfg)
    exit_thr = compute_exit_threshold(cfg, entry)
    assert exit_thr == entry * cfg.exit_threshold_mult


def test_exit_signal_threshold_override() -> None:
    cfg = PredictorTimesFMConfig(
        timeframe="1m",
        exit_signal_threshold=0.0005,
        safety_margin=0.0001,
    )
    entry = compute_entry_threshold(cfg)
    assert compute_exit_threshold(cfg, entry) == 0.0005
