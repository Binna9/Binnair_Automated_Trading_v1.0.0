"""OHLCV OHLC 기반 시장 레짐·ATR TP/SL."""

from __future__ import annotations

from binnair_trading_engine.autopilot.models import AutopilotConfig, RegimeSnapshot

# bars 원소 타입: (high, low, close), 오래된 순.
Bar = tuple[float, float, float]


def _ema(values: list[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    k = 2.0 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1.0 - k)
    return ema


def _true_range(high: float, low: float, prev_close: float) -> float:
    """당일 고저폭 + 전일 종가 갭까지 반영한 True Range."""
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _atr_from_bars(bars: list[Bar], period: int) -> float:
    """High/Low 기반 True Range 평균 ATR.

    close 차분만 쓰면 캔들 내 변동폭(꼬리)이 통째로 빠져 ATR이 실제
    변동성보다 작게 잡히고, 그 결과로 SL이 스프레드/슬리피지보다도
    좁아지는 사례가 있어 True Range로 계산한다.
    """
    if len(bars) < 2:
        return 0.0
    trs = [
        _true_range(bars[i][0], bars[i][1], bars[i - 1][2])
        for i in range(1, len(bars))
    ]
    use = trs[-period:] if len(trs) >= period else trs
    return sum(use) / len(use) if use else 0.0


def _atr_series(bars: list[Bar], period: int) -> list[float]:
    if len(bars) < period + 1:
        return []
    out: list[float] = []
    for i in range(period, len(bars)):
        window = bars[i - period : i + 1]
        out.append(_atr_from_bars(window, period))
    return out


class RegimeDetector:
    def __init__(self, config: AutopilotConfig) -> None:
        self._cfg = config

    def detect(self, bars: list[Bar], price: float) -> RegimeSnapshot:
        cfg = self._cfg
        closes = [b[2] for b in bars]
        if len(bars) < max(cfg.atr_period + 2, cfg.ema_slow + 2) or price <= 0:
            return RegimeSnapshot(
                label="unknown",
                atr=0.0,
                atr_pct=0.0,
                trend_slope=0.0,
                tp_atr_mult=cfg.base_tp_atr_mult,
                sl_atr_mult=cfg.base_sl_atr_mult,
            )

        atr = _atr_from_bars(bars, cfg.atr_period)
        atr_pct = atr / price if price > 0 else 0.0

        atr_hist = _atr_series(bars, cfg.atr_period)
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
            threshold_mult = cfg.high_vol_threshold_mult
            consecutive_delta = max(0, int(cfg.high_vol_consecutive_delta))
            position_scale = max(0.1, min(1.0, float(cfg.high_vol_position_scale)))
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
        min_tp_pct: float = 0.0,
        min_sl_pct: float = 0.0,
    ) -> tuple[float, float]:
        """ATR 배수 → tp_pct / sl_pct (PassthroughStrategy용).

        min_tp_pct/min_sl_pct: 왕복 수수료+슬리피지 원가 이하로 좁혀지지
        않도록 하는 하한. ATR이 순간적으로 작게 측정되면 SL이 원가보다도
        좁아져 진입 직후 사실상 확정 손절되는 구간이 생길 수 있어 강제한다.
        """
        if price <= 0 or atr <= 0:
            return 0.0, 0.0
        sl_pct = max((atr * sl_atr_mult) / price, min_sl_pct)
        tp_pct = max((atr * tp_atr_mult) / price, min_tp_pct)
        return max(tp_pct, 0.0), max(sl_pct, 0.0)
