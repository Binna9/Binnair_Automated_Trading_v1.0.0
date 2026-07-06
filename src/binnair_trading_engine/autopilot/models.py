"""Autopilot 설정·상태 DTO."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AutopilotConfig:
    """autopilot env (BINNAIR_AUTOPILOT_*)."""

    enabled: bool = False
    # --- Auto-Calibration (TimesFM threshold) ---
    score_window: int = 500
    score_min_samples: int = 30
    score_percentile: float = 70.0
    score_k: float = 1.0
    # --- Regime (ATR / trend) ---
    atr_period: int = 14
    ema_fast: int = 12
    ema_slow: int = 26
    vol_lookback: int = 100
    high_vol_ratio: float = 1.35
    low_vol_ratio: float = 0.75
    trend_slope_threshold: float = 0.0015
    # ATR 배수 (프로필 기본 — regime이 곱함)
    base_tp_atr_mult: float = 2.0
    base_sl_atr_mult: float = 1.2
    base_consecutive_required: int = 2
    status_log_every_ticks: int = 10


@dataclass
class RegimeSnapshot:
    """현재 시장 레짐 + 조정 계수."""

    label: str
    atr: float
    atr_pct: float
    trend_slope: float
    threshold_multiplier: float = 1.0
    consecutive_delta: int = 0
    position_scale: float = 1.0
    tp_atr_mult: float = 2.0
    sl_atr_mult: float = 1.2


@dataclass
class AutopilotState:
    """tick마다 갱신 — 로그·API·JSON persist 노출용."""

    enabled: bool = False
    tick_count: int = 0
    regime: str = "unknown"
    atr: float = 0.0
    atr_pct: float = 0.0
    trend_slope: float = 0.0
    base_threshold: float = 0.0
    regime_threshold_mult: float = 1.0
    effective_threshold: float = 0.0
    fee_floor: float = 0.0
    min_threshold: float = 0.0
    score_samples: int = 0
    consecutive_required: int = 2
    tp_pct: float = 0.0
    sl_pct: float = 0.0
    tp_atr_mult: float = 0.0
    sl_atr_mult: float = 0.0
    position_scale: float = 1.0
    symbol: str = ""
    run_id: str = ""
    user_id: str = "default"
    updated_at: str = ""
    extra: dict = field(default_factory=dict)
