"""Autopilot calibration tests."""

from binnair_trading_engine.autopilot.calibration import ThresholdCalibrator


def test_compute_threshold_respects_min_not_fee_floor():
    cal = ThresholdCalibrator(min_samples=5, percentile=70.0, k=1.0)
    cal.load_scores([0.0001, 0.00015, 0.0002, 0.00025, 0.0003])
    # fee_floor would be ~0.0014; min_threshold 0.00008 must win over adaptive floor
    result = cal.compute_threshold(0.00008)
    assert result >= 0.00008
    assert result < 0.001


def test_compute_threshold_evolves_with_percentile():
    cal = ThresholdCalibrator(min_samples=3, percentile=70.0, k=1.0)
    cal.load_scores([0.00005, 0.00010, 0.00020, 0.00030, 0.00040])
    evolved = cal.compute_threshold(0.00008)
    assert evolved >= 0.00008
    assert evolved <= 0.00040


def test_load_scores_respects_window():
    cal = ThresholdCalibrator(window=10, min_samples=1)
    cal.load_scores([0.1] * 15)
    assert cal.sample_count == 10
