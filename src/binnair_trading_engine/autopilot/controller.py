"""Autopilot tick orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from binnair_trading_engine.autopilot.calibration import ThresholdCalibrator
from binnair_trading_engine.autopilot.models import AutopilotConfig, AutopilotState
from binnair_trading_engine.autopilot.persist import (
    AutopilotStateStore,
    resolve_autopilot_state_path,
)
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
        *,
        state_persist_path: Path | None = None,
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
        self._last_regime_label: str | None = None
        self._run_id = ""
        self._user_id = "default"
        self.last_state = AutopilotState(enabled=config.enabled)
        self._state_store: AutopilotStateStore | None = None
        if state_persist_path is not None:
            ap_path = resolve_autopilot_state_path(state_persist_path)
            self._state_store = AutopilotStateStore(ap_path)

    def _fee_floor(self) -> float:
        c = self._timesfm_config
        return c.fee_rate * 2.0 + c.slippage_rate + c.safety_margin

    def _min_threshold(self) -> float:
        from binnair_trading_engine.predictor.timesfm_utils import compute_entry_threshold

        return compute_entry_threshold(self._timesfm_config)

    def _load_bars(self, symbol: str) -> list[tuple[float, float, float]]:
        """(high, low, close) 바 목록 — True Range ATR 계산용."""
        if self._price_history is None:
            return []
        try:
            need = max(
                self._cfg.vol_lookback + self._cfg.atr_period + 5,
                self._cfg.ema_slow + 5,
            )
            return self._price_history.get_recent_ohlc(
                symbol=symbol,
                timeframe=self._timesfm_config.timeframe,
                limit=need,
            )
        except Exception as e:
            logger.debug("Autopilot OHLCV load failed: %s", e)
            return []

    def initialize(
        self,
        *,
        run_id: str,
        user_id: str,
        symbol: str,
        storage_backend: str,
    ) -> None:
        """기동 시 JSON 상태 복구 + DB inference score warmup."""
        self._run_id = run_id
        self._user_id = user_id

        if self._state_store is not None:
            loaded = self._state_store.load()
            if loaded and loaded.run_id == run_id:
                self._tick = loaded.tick_count
                self._last_regime_label = (
                    loaded.regime if loaded.regime not in ("", "unknown") else None
                )
                logger.info(
                    "Autopilot state restored: tick=%d regime=%s path=%s",
                    self._tick,
                    loaded.regime,
                    self._state_store.path,
                )

        if storage_backend == "postgres":
            warmed = self._warmup_scores_from_db(run_id, user_id, symbol)
            logger.info(
                "Autopilot DB warmup: symbol=%s scores_loaded=%d calibrator_samples=%d",
                symbol,
                warmed,
                self._calibrator.sample_count,
            )

        logger.info(
            "Autopilot initialized: run_id=%s symbol=%s min_threshold=%.6f samples=%d",
            run_id,
            symbol,
            self._min_threshold(),
            self._calibrator.sample_count,
        )

    def _warmup_scores_from_db(
        self,
        run_id: str,
        user_id: str,
        symbol: str,
    ) -> int:
        try:
            from binnair_trading_engine.infra.persistence.repositories.postgres import (
                PostgresRepositoryFactory,
            )

            repo = PostgresRepositoryFactory().model_inference_event
            scores = repo.get_recent_scores(
                run_id=run_id,
                symbol=symbol,
                user_id=user_id,
                limit=self._cfg.score_window,
            )
            if scores:
                self._calibrator.load_scores(scores)
            return len(scores)
        except Exception as e:
            logger.warning("Autopilot DB score warmup failed: %s", e)
            return 0

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
            self.last_state = AutopilotState(enabled=False, symbol=symbol, run_id=self._run_id)
            return self.last_state

        bars = self._load_bars(symbol)
        regime = self._regime.detect(bars, price)

        min_threshold = self._min_threshold()
        fee_floor = self._fee_floor()
        base_threshold = self._calibrator.compute_threshold(min_threshold)
        effective = base_threshold * regime.threshold_multiplier

        if isinstance(predictor, TimesFMPredictor):
            from binnair_trading_engine.predictor.timesfm_utils import compute_exit_threshold

            exit_thr = compute_exit_threshold(self._timesfm_config, effective)
            predictor.set_thresholds(effective, exit_thr)

        base_consecutive = self._cfg.base_consecutive_required
        consecutive = max(1, base_consecutive + regime.consecutive_delta)
        signal_policy.set_consecutive_required(consecutive)

        tp_pct, sl_pct = RegimeDetector.tp_sl_pct(
            price,
            regime.atr,
            regime.tp_atr_mult,
            regime.sl_atr_mult,
            min_tp_pct=fee_floor,
            min_sl_pct=fee_floor,
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
            min_threshold=min_threshold,
            score_samples=self._calibrator.sample_count,
            consecutive_required=consecutive,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            tp_atr_mult=regime.tp_atr_mult,
            sl_atr_mult=regime.sl_atr_mult,
            position_scale=regime.position_scale,
            symbol=symbol,
            run_id=self._run_id,
            user_id=self._user_id,
            extra={
                "ohlcv_bars": len(bars),
                "vol_lookback": self._cfg.vol_lookback,
            },
        )
        prev_effective = (
            self.last_state.effective_threshold
            if self._last_regime_label is not None
            else 0.0
        )
        self.last_state = state
        self._log_regime_change(state, prev_effective=prev_effective)
        self._persist_state(state)

        if self._tick % max(1, self._cfg.status_log_every_ticks) == 0:
            logger.info(
                "Autopilot: regime=%s threshold=%.6f (base=%.6f x%.2f min=%.6f fee_ref=%.6f) "
                "tp_pct=%.4f sl_pct=%.4f consecutive=%d position_scale=%.2f samples=%d",
                state.regime,
                state.effective_threshold,
                state.base_threshold,
                state.regime_threshold_mult,
                state.min_threshold,
                state.fee_floor,
                state.tp_pct,
                state.sl_pct,
                state.consecutive_required,
                state.position_scale,
                state.score_samples,
            )
        return state

    def _log_regime_change(
        self,
        state: AutopilotState,
        *,
        prev_effective: float,
    ) -> None:
        if self._last_regime_label == state.regime:
            return
        prev = self._last_regime_label or "(start)"
        logger.info(
            "Autopilot regime changed: %s -> %s | threshold %.6f -> %.6f "
            "(base=%.6f x%.2f) consecutive=%d tp=%.4f sl=%.4f ohlcv_bars=%s",
            prev,
            state.regime,
            prev_effective,
            state.effective_threshold,
            state.base_threshold,
            state.regime_threshold_mult,
            state.consecutive_required,
            state.tp_pct,
            state.sl_pct,
            state.extra.get("ohlcv_bars"),
        )
        self._last_regime_label = state.regime

    def _persist_state(self, state: AutopilotState) -> None:
        if self._state_store is None:
            return
        try:
            self._state_store.save(state)
        except Exception as e:
            logger.warning("Autopilot state persist failed: %s", e)

    def record_prediction_score(self, score: float | None) -> None:
        if self._cfg.enabled:
            self._calibrator.record(score)
