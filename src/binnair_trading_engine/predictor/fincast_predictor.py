"""
FinCast 사전학습 가중치로 미래 가격을 예측한다.
TimesFMPredictor와 동일하게 close 시계열 → expected return → BUY/HOLD/SELL.
"""
from __future__ import annotations

import logging
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from binnair_trading_engine.config.settings import PredictorFinCastConfig
from binnair_trading_engine.domain.models import (
    MarketSnapshot,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.market_data import PriceHistoryProvider
from binnair_trading_engine.predictor.interface import Predictor
from binnair_trading_engine.predictor.timesfm_utils import (
    compute_entry_threshold,
    compute_exit_threshold,
)

logger = logging.getLogger(__name__)

HOLD_MODEL_UNLOADED = "model_unloaded"
HOLD_INSUFFICIENT_CONTEXT = "insufficient_context"
HOLD_INFERENCE_ERROR = "inference_error"
HOLD_AWAITING_CANDLE = "awaiting_candle_close"
HOLD_BELOW_THRESHOLD = "below_threshold"


class FinCastPredictor(Predictor):
    """
    FinCast zero-shot forecast → BUY/SELL/HOLD soft candidate.

    FinCast-fts의 `ffm` 패키지와 로컬 `.pth` 체크포인트가 필요하다.
    로드 실패 시 HOLD(model_unloaded) — 엔진은 계속 동작한다.
    """

    def __init__(
        self,
        config: PredictorFinCastConfig,
        price_history_provider: PriceHistoryProvider | None = None,
    ) -> None:
        self._config = config
        self._price_history: deque[float] = deque(maxlen=config.context_length)
        self._model: Any = None
        self._price_history_provider = price_history_provider
        self._price_history_provider_failed = False
        self._entry_threshold = compute_entry_threshold(config)
        self._exit_threshold = compute_exit_threshold(config, self._entry_threshold)
        self._last_infer_candle_open_time: dict[str, datetime] = {}
        self._initial_entry_threshold = self._entry_threshold
        self._forecast_mode = (config.forecast_mode or "average").lower()
        if self._forecast_mode not in ("average", "last"):
            logger.warning(
                "Unknown forecast_mode=%r, using average",
                config.forecast_mode,
            )
            self._forecast_mode = "average"
        logger.info(
            "FinCast thresholds: entry=%.6f exit=%.6f timeframe=%s "
            "forecast_mode=%s checkpoint=%s",
            self._entry_threshold,
            self._exit_threshold,
            config.timeframe,
            self._forecast_mode,
            config.checkpoint_path or "(empty)",
        )
        self._load_model()

    def _ensure_repo_on_path(self) -> None:
        repo = (self._config.repo_path or "").strip()
        if not repo:
            return
        path = str(Path(repo).expanduser().resolve())
        if path not in sys.path:
            sys.path.insert(0, path)

    def _load_model(self) -> None:
        checkpoint = (self._config.checkpoint_path or "").strip()
        if not checkpoint:
            logger.warning("FinCast checkpoint_path empty — HOLD fallback")
            self._model = None
            return
        ckpt = Path(checkpoint).expanduser()
        if not ckpt.is_file():
            logger.warning("FinCast checkpoint not found: %s", ckpt)
            self._model = None
            return
        try:
            self._ensure_repo_on_path()
            from ffm import FFM, FFmHparams  # type: ignore[import-not-found]

            backend = (self._config.backend or "gpu").lower()
            if backend not in ("cpu", "gpu", "tpu"):
                backend = "gpu"
            point_mode = (self._config.point_forecast_mode or "mean").lower()
            if point_mode not in ("mean", "median"):
                point_mode = "mean"

            hparams = FFmHparams(
                backend=backend,
                per_core_batch_size=32,
                horizon_len=max(1, self._config.horizon),
                context_len=max(32, self._config.context_length),
                use_positional_embedding=False,
                num_experts=max(1, self._config.num_experts),
                gating_top_n=max(1, self._config.gating_top_n),
                load_from_compile=bool(self._config.load_from_compile),
                point_forecast_mode=point_mode,
            )
            model = FFM(hparams=hparams, checkpoint=str(ckpt), loading_mode=0)
            model.model_eval_mode()
            self._model = model
            logger.info("FinCast model loaded from %s (backend=%s)", ckpt, backend)
        except Exception as e:
            logger.warning("FinCast model load failed, using HOLD fallback: %s", e)
            self._model = None

    def set_threshold(self, value: float) -> None:
        if value > 0:
            self._entry_threshold = float(value)
            self._exit_threshold = compute_exit_threshold(
                self._config, self._entry_threshold
            )

    def set_thresholds(self, entry: float, exit: float | None = None) -> None:
        if entry > 0:
            self._entry_threshold = float(entry)
        if exit is not None and exit > 0:
            self._exit_threshold = float(exit)
        else:
            self._exit_threshold = compute_exit_threshold(
                self._config, self._entry_threshold
            )

    def get_threshold(self) -> float:
        return self._entry_threshold

    def get_exit_threshold(self) -> float:
        return self._exit_threshold

    def get_initial_threshold(self) -> float:
        return getattr(self, "_initial_entry_threshold", self._entry_threshold)

    def predict(
        self,
        snapshot: MarketSnapshot,
        ctx: TradeContext,
        *,
        for_exit: bool = False,
    ) -> Prediction | None:
        signal_kind = "exit" if for_exit else "entry"
        threshold = self._exit_threshold if for_exit else self._entry_threshold

        if self._config.predict_on_candle_close and not self._is_new_candle(
            snapshot.symbol
        ):
            return self._hold(
                snapshot,
                hold_reason=HOLD_AWAITING_CANDLE,
                effective_threshold=threshold,
                signal_kind=signal_kind,
            )

        self._price_history.append(float(snapshot.price))

        history = self._get_price_history(snapshot)
        if self._model is None:
            return self._hold(
                snapshot,
                hold_reason=HOLD_MODEL_UNLOADED,
                effective_threshold=threshold,
                signal_kind=signal_kind,
            )
        if len(history) < self._config.min_context:
            return self._hold(
                snapshot,
                hold_reason=HOLD_INSUFFICIENT_CONTEXT,
                effective_threshold=threshold,
                signal_kind=signal_kind,
            )

        try:
            current_price = float(snapshot.price)
            history_arr = np.asarray(history, dtype=np.float32)
            point_forecast, _ = self._model.forecast(
                inputs=[history_arr],
                freq=[int(self._config.freq)],
                forecast_context_len=self._config.context_length,
                return_forecast_on_context=False,
                normalize=bool(self._config.normalize_inputs),
            )
            forecast_prices = self._parse_forecast_prices(point_forecast)
            forecast_returns = self._step_returns(current_price, forecast_prices)
            expected_return = self._aggregate_return(forecast_returns)
            action = self._to_action(expected_return, threshold)
            confidence = self._to_confidence(expected_return, threshold)
            hold_reason = (
                HOLD_BELOW_THRESHOLD if action == SignalAction.HOLD else None
            )

            if self._config.predict_on_candle_close:
                open_time = self._fetch_latest_candle_open_time(snapshot.symbol)
                if open_time is not None:
                    self._last_infer_candle_open_time[snapshot.symbol] = open_time

            return Prediction(
                action=action,
                confidence=confidence,
                price_hint=current_price,
                score=expected_return,
                probability=self._to_probability(action, confidence),
                model_version=self._config.model_version or ctx.model_version,
                feature_set_version=(
                    self._config.feature_set_version or ctx.feature_set_version
                ),
                forecast_mode=self._forecast_mode,
                forecast_prices=forecast_prices,
                forecast_returns=forecast_returns,
                hold_reason=hold_reason,
                effective_threshold=threshold,
                signal_kind=signal_kind,
            )
        except Exception as e:
            logger.exception("FinCast inference failed: %s", e)
            return self._hold(
                snapshot,
                hold_reason=HOLD_INFERENCE_ERROR,
                effective_threshold=threshold,
                signal_kind=signal_kind,
            )

    def _is_new_candle(self, symbol: str) -> bool:
        open_time = self._fetch_latest_candle_open_time(symbol)
        if open_time is None:
            return True
        prev = self._last_infer_candle_open_time.get(symbol)
        if prev is None or open_time > prev:
            return True
        return False

    def _fetch_latest_candle_open_time(self, symbol: str) -> datetime | None:
        if self._price_history_provider is None:
            return None
        getter = getattr(
            self._price_history_provider, "get_latest_candle_open_time", None
        )
        if getter is None:
            return None
        try:
            return getter(symbol=symbol, timeframe=self._config.timeframe)
        except Exception as e:
            logger.debug("Latest candle open_time lookup failed: %s", e)
            return None

    def _get_price_history(self, snapshot: MarketSnapshot) -> list[float]:
        if not self._config.use_ohlcv_history or self._price_history_provider is None:
            return list(self._price_history)

        closes = self._get_external_history(snapshot.symbol)
        if len(closes) >= self._config.min_context:
            if self._config.append_live_price_to_history:
                current_price = float(snapshot.price)
                if not closes or closes[-1] != current_price:
                    closes.append(current_price)
            return closes[-self._config.context_length :]

        return list(self._price_history)

    def _get_external_history(self, symbol: str) -> list[float]:
        if self._price_history_provider_failed or self._price_history_provider is None:
            return []
        try:
            return self._price_history_provider.get_recent_prices(
                symbol=symbol,
                timeframe=self._config.timeframe,
                limit=self._config.context_length,
            )
        except Exception as e:
            self._price_history_provider_failed = True
            logger.warning(
                "Price history load failed, using in-memory tick history: %s",
                e,
            )
            return []

    def _parse_forecast_prices(self, point_forecast: Any) -> list[float]:
        forecast = np.asarray(point_forecast, dtype=np.float64)
        row = forecast[0]
        return [float(p) for p in row[: self._config.horizon]]

    def _step_returns(
        self, current_price: float, forecast_prices: list[float]
    ) -> list[float]:
        if current_price <= 0:
            return [0.0 for _ in forecast_prices]
        return [(p - current_price) / current_price for p in forecast_prices]

    def _aggregate_return(self, forecast_returns: list[float]) -> float:
        if not forecast_returns:
            return 0.0
        if self._forecast_mode == "last":
            idx = self._config.forecast_index
            if idx < 0:
                idx = len(forecast_returns) + idx
            idx = max(0, min(idx, len(forecast_returns) - 1))
            return float(forecast_returns[idx])
        return float(sum(forecast_returns) / len(forecast_returns))

    def _to_action(self, expected_return: float, threshold: float) -> SignalAction:
        if expected_return > threshold:
            return SignalAction.BUY
        if expected_return < -threshold:
            return SignalAction.SELL
        return SignalAction.HOLD

    def _to_confidence(self, expected_return: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        return min(1.0, abs(expected_return) / threshold)

    def _to_probability(
        self,
        action: SignalAction,
        confidence: float,
    ) -> dict[str, float]:
        hold_probability = max(0.0, 1.0 - confidence)
        side_probability = confidence
        return {
            SignalAction.BUY.value: side_probability
            if action == SignalAction.BUY
            else 0.0,
            SignalAction.SELL.value: side_probability
            if action == SignalAction.SELL
            else 0.0,
            SignalAction.HOLD.value: 1.0
            if action == SignalAction.HOLD
            else hold_probability,
        }

    def _hold(
        self,
        snapshot: MarketSnapshot,
        *,
        hold_reason: str,
        effective_threshold: float | None = None,
        signal_kind: str = "entry",
    ) -> Prediction:
        return Prediction(
            action=SignalAction.HOLD,
            confidence=0.0,
            price_hint=snapshot.price,
            score=0.0,
            probability={
                SignalAction.BUY.value: 0.0,
                SignalAction.SELL.value: 0.0,
                SignalAction.HOLD.value: 1.0,
            },
            model_version=self._config.model_version,
            feature_set_version=self._config.feature_set_version,
            forecast_mode=self._forecast_mode,
            hold_reason=hold_reason,
            effective_threshold=effective_threshold,
            signal_kind=signal_kind,
        )
