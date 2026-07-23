"""high_vol 진입 축소 (Risk-first Phase2)."""

from __future__ import annotations

from binnair_trading_engine.autopilot.models import AutopilotConfig
from binnair_trading_engine.autopilot.regime import RegimeDetector


def _bars_high_vol(n: int = 120) -> list[tuple[float, float, float]]:
    """중간 ATR 후 후반에 변동성 급증."""
    bars: list[tuple[float, float, float]] = []
    px = 1.0
    for i in range(n):
        if i < 80:
            w = 0.001
        else:
            w = 0.01
        high = px + w
        low = px - w
        close = px + (0.0001 if i % 2 == 0 else -0.0001)
        bars.append((high, low, close))
        px = close
    return bars


def test_high_vol_uses_tighter_entry_defaults():
    cfg = AutopilotConfig(
        high_vol_ratio=1.2,
        high_vol_position_scale=0.5,
        high_vol_consecutive_delta=2,
        high_vol_threshold_mult=1.5,
        base_consecutive_required=2,
    )
    det = RegimeDetector(cfg)
    bars = _bars_high_vol()
    snap = det.detect(bars, price=bars[-1][2])
    assert snap.label == "high_vol"
    assert snap.position_scale == 0.5
    assert snap.consecutive_delta == 2
    assert snap.threshold_multiplier == 1.5


def test_high_vol_config_override():
    cfg = AutopilotConfig(
        high_vol_ratio=1.2,
        high_vol_position_scale=0.4,
        high_vol_consecutive_delta=3,
    )
    det = RegimeDetector(cfg)
    snap = det.detect(_bars_high_vol(), price=1.0)
    assert snap.label == "high_vol"
    assert snap.position_scale == 0.4
    assert snap.consecutive_delta == 3
