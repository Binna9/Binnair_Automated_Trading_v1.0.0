"""Autopilot tick orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from binnair_trading_engine.autopilot.calibration import ThresholdCalibrator
from binnair_trading_engine.autopilot.models import AutopilotConfig, AutopilotState
from binnair_trading_engine.autopilot.regime import RegimeDetector
from binnair_trading_engine.config.settings import PredictorTimesFMConfig
from binnair_trading_engine.predictor.timesfm_predictor import TimesFMPredictor
from binnair_trading_engine.signal.policy import ConsecutiveSignalPolicy
from binnair_trading_engine.strategy.passthrough import PassthroughStrategy

if TYPE_CHECKING:
    from binnair_trading_engine.market_data.history import PriceHistoryProvider

logger = logging.getLogger(__name__)


class AutopilotController:
    """매 tick threshold·TP/SL·consecutive 자동 적용."""

    def __init__(
        self,
        config: AutopilotConfig,
        timesfm_config: PredictorTimesFMConfig | None,
        price_history_provider: PriceHistoryProvider | None = None,
    ) -> None:
        self._cfg = config
        self._timesfm_config = timesfm_config or PredictorTimesFMConfig()
        self._price_history = price_history_provider
        self._calibrator = ThresholdCalibrator(
            window=config.score_window,
            min_samples=config.score_min_samples,
            percentile=config.score_percentile,
            k=config.score_k,
        )
        self._regime = RegimeDetector(config)
        self._tick = 0
        self.last_state = AutopilotState(enabled=config.enabled)

    def _fee_floor(self) -> float:
        c = self._timesfm_config
        return c.fee_rate * 2.0 + c.slippage_rate + c.safety_margin

    def _fallback_threshold(self) -> float:
        c = self._timesfm_config
        if c.signal_threshold is not None:
            return float(c.signal_threshold)
        return self._fee_floor()

    def _load_closes(self, symbol: str) -> list[float]:
        if self._price_history is None:
            return []
        try:
            need = max(
                self._cfg.vol_lookback + self._cfg.atr_period + 5,
                self._cfg.ema_slow + 5,
            )
            return self._price_history.get_recent_prices(
                symbol=symbol,
                timeframe=self._timesfm_config.timeframe,
                limit=need,
            )
        except Exception as e:
            logger.debug("Autopilot OHLCV load failed: %s", e)
            return []

    def apply_before_predict(
        self,
        *,
        symbol: str,
        price: float,
        predictor,
        signal_policy: ConsecutiveSignalPolicy,
        strategy: PassthroughStrategy | None,
    ) -> AutopilotState:
        """predict() 직전 — threshold·TP/SL·consecutive 갱신."""
        self._tick += 1
        if not self._cfg.enabled:
            self.last_state = AutopilotState(enabled=False, symbol=symbol)
            return self.last_state

        closes = self._load_closes(symbol)
        regime = self._regime.detect(closes, price)

        fee_floor = self._fee_floor()
        base_threshold = self._calibrator.compute_threshold(
            fee_floor, self._fallback_threshold()
        )
        effective = base_threshold * regime.threshold_multiplier

        if isinstance(predictor, TimesFMPredictor):
            predictor.set_threshold(effective)

        base_consecutive = self._cfg.base_consecutive_required
        consecutive = max(1, base_consecutive + regime.consecutive_delta)
        signal_policy.set_consecutive_required(consecutive)

        tp_pct, sl_pct = RegimeDetector.tp_sl_pct(
            price,
            regime.atr,
            regime.tp_atr_mult,
            regime.sl_atr_mult,
        )
        if strategy is not None and tp_pct > 0 and sl_pct > 0:
            strategy.set_dynamic_exit(
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                position_scale=regime.position_scale,
            )

        state = AutopilotState(
            enabled=True,
            tick_count=self._tick,
            regime=regime.label,
            atr=regime.atr,
            atr_pct=regime.atr_pct,
            trend_slope=regime.trend_slope,
            base_threshold=base_threshold,
            regime_threshold_mult=regime.threshold_multiplier,
            effective_threshold=effective,
            fee_floor=fee_floor,
            score_samples=self._calibrator.sample_count,
            consecutive_required=consecutive,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            tp_atr_mult=regime.tp_atr_mult,
            sl_atr_mult=regime.sl_atr_mult,
            position_scale=regime.position_scale,
            symbol=symbol,
        )
        self.last_state = state

        if self._tick % max(1, self._cfg.status_log_every_ticks) == 0:
            logger.info(
                "Autopilot: regime=%s threshold=%.6f (base=%.6f x%.2f) "
                "tp_pct=%.4f sl_pct=%.4f consecutive=%d position_scale=%.2f samples=%d",
                state.regime,
                state.effective_threshold,
                state.base_threshold,
                state.regime_threshold_mult,
                state.tp_pct,
                state.sl_pct,
                state.consecutive_required,
                state.position_scale,
                state.score_samples,
            )
        return state

    def record_prediction_score(self, score: float | None) -> None:
        if self._cfg.enabled:
            self._calibrator.record(score)
