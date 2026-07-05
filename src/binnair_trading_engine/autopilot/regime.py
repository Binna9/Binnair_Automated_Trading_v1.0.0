"""OHLCV close 기반 시장 레짐·ATR TP/SL."""

from __future__ import annotations

from binnair_trading_engine.autopilot.models import AutopilotConfig, RegimeSnapshot


def _ema(values: list[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    k = 2.0 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1.0 - k)
    return ema


def _atr_from_closes(closes: list[float], period: int) -> float:
    """H/L 없을 때 close 차분 평균으로 ATR 근사."""
    if len(closes) < 2:
        return 0.0
    trs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    use = trs[-period:] if len(trs) >= period else trs
    return sum(use) / len(use) if use else 0.0


def _atr_series(closes: list[float], period: int) -> list[float]:
    if len(closes) < period + 1:
        return []
    out: list[float] = []
    for i in range(period, len(closes)):
        window = closes[i - period : i + 1]
        out.append(_atr_from_closes(window, period))
    return out


class RegimeDetector:
    def __init__(self, config: AutopilotConfig) -> None:
        self._cfg = config

    def detect(self, closes: list[float], price: float) -> RegimeSnapshot:
        cfg = self._cfg
        if len(closes) < max(cfg.atr_period + 2, cfg.ema_slow + 2) or price <= 0:
            return RegimeSnapshot(
                label="unknown",
                atr=0.0,
                atr_pct=0.0,
                trend_slope=0.0,
                tp_atr_mult=cfg.base_tp_atr_mult,
                sl_atr_mult=cfg.base_sl_atr_mult,
            )

        atr = _atr_from_closes(closes, cfg.atr_period)
        atr_pct = atr / price if price > 0 else 0.0

        atr_hist = _atr_series(closes, cfg.atr_period)
        lookback = atr_hist[-cfg.vol_lookback :] if atr_hist else []
        median_atr = sorted(lookback)[len(lookback) // 2] if lookback else atr
        vol_ratio = (atr / median_atr) if median_atr > 0 else 1.0

        ema_fast = _ema(closes[-cfg.ema_slow :], cfg.ema_fast)
        ema_slow = _ema(closes[-cfg.ema_slow :], cfg.ema_slow)
        trend_slope = (ema_fast - ema_slow) / price

        high_vol = vol_ratio >= cfg.high_vol_ratio
        low_vol = vol_ratio <= cfg.low_vol_ratio
        trending = abs(trend_slope) >= cfg.trend_slope_threshold
        ranging = not trending

        label = "normal"
        threshold_mult = 1.0
        consecutive_delta = 0
        position_scale = 1.0
        tp_mult = cfg.base_tp_atr_mult
        sl_mult = cfg.base_sl_atr_mult

        if high_vol:
            label = "high_vol"
            threshold_mult = 1.5
            consecutive_delta = 1
            position_scale = 0.7
            sl_mult = cfg.base_sl_atr_mult * 1.25
        elif low_vol:
            label = "low_vol"
            threshold_mult = 0.85
            position_scale = 1.0
        elif ranging:
            label = "ranging"
            threshold_mult = 1.2
            consecutive_delta = 1
        elif trending:
            label = "trending"
            tp_mult = cfg.base_tp_atr_mult * 1.25
            sl_mult = cfg.base_sl_atr_mult * 1.0

        return RegimeSnapshot(
            label=label,
            atr=atr,
            atr_pct=atr_pct,
            trend_slope=trend_slope,
            threshold_multiplier=threshold_mult,
            consecutive_delta=consecutive_delta,
            position_scale=position_scale,
            tp_atr_mult=tp_mult,
            sl_atr_mult=sl_mult,
        )

    @staticmethod
    def tp_sl_pct(
        price: float,
        atr: float,
        tp_atr_mult: float,
        sl_atr_mult: float,
        side: str = "LONG",
    ) -> tuple[float, float]:
        """ATR 배수 → tp_pct / sl_pct (PassthroughStrategy용)."""
        if price <= 0 or atr <= 0:
            return 0.0, 0.0
        sl_pct = (atr * sl_atr_mult) / price
        tp_pct = (atr * tp_atr_mult) / price
        return max(tp_pct, 0.0), max(sl_pct, 0.0)
