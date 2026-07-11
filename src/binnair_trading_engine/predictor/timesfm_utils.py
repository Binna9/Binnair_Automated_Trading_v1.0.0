"""
TimesFM threshold·timeframe 유틸.

timeframe 변경 시 score 스케일과 fee floor(왕복 원가)를 맞추고,
poll interval과 캔들 주기 정렬에 쓴다.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binnair_trading_engine.config.settings import PredictorTimesFMConfig

_TIMEFRAME_RE = re.compile(r"^(\d+)([mhdw])$", re.IGNORECASE)
_UNIT_MINUTES = {"m": 1, "h": 60, "d": 1440, "w": 10080}


def timeframe_to_minutes(timeframe: str) -> float:
    """Binance interval 문자열 → 분 (예: 5m → 5, 1h → 60)."""
    tf = (timeframe or "1m").strip().lower()
    match = _TIMEFRAME_RE.match(tf)
    if not match:
        return 1.0
    amount = int(match.group(1))
    unit = match.group(2).lower()
    return float(amount * _UNIT_MINUTES.get(unit, 1))


def timeframe_to_seconds(timeframe: str) -> int:
    return max(1, int(timeframe_to_minutes(timeframe) * 60))


def compute_fee_floor(
    *,
    fee_rate: float,
    slippage_rate: float,
    safety_margin: float,
) -> float:
    """왕복 거래 원가 하한 (fee×2 + slippage + safety)."""
    return fee_rate * 2.0 + slippage_rate + safety_margin


def compute_entry_threshold(
    config: "PredictorTimesFMConfig",
) -> float:
    """
    진입(BUY) 판정 threshold.

    signal_threshold가 지정되면 그대로 사용.
    아니면 fee_floor를 timeframe·horizon에 맞게 스케일 (긴 봉일수록 |score|가 작아지는 보정).
    """
    if config.signal_threshold is not None:
        return float(config.signal_threshold)

    floor = compute_fee_floor(
        fee_rate=config.fee_rate,
        slippage_rate=config.slippage_rate,
        safety_margin=config.safety_margin,
    )
    if not config.timeframe_threshold_scale:
        return floor

    tf_min = timeframe_to_minutes(config.timeframe)
    ref_min = timeframe_to_minutes(config.ref_timeframe)
    ref_horizon = max(1, config.ref_horizon)
    horizon = max(1, config.horizon)

    # 긴 timeframe → wall-clock 대비 step return 축소 → threshold 비례 하향
    time_factor = max(ref_min / tf_min, 0.15)
    horizon_factor = max(float(ref_horizon) / float(horizon), 0.5)
    scaled = floor * time_factor * horizon_factor
    # 원가 이하로는 내리지 않음 (경제적 무의미 거래 방지)
    return max(scaled, floor * config.min_threshold_fee_ratio)


def compute_exit_threshold(
    config: "PredictorTimesFMConfig",
    entry_threshold: float,
) -> float:
    """청산(SELL/BUY) 판정 threshold — 모델 기반 청산용."""
    if config.exit_signal_threshold is not None:
        return float(config.exit_signal_threshold)
    mult = max(0.1, config.exit_threshold_mult)
    return entry_threshold * mult
