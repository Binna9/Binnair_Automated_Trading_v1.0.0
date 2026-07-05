"""
TimesFM 사전학습 모델로 미래 가격을 예측한다.
horizon 스텝 forecast를 expected return으로 바꿔 BUY/HOLD/SELL을 산출한다.
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Any

import numpy as np

from binnair_trading_engine.config.settings import PredictorTimesFMConfig
from binnair_trading_engine.domain.models import (
    MarketSnapshot,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.market_data import PriceHistoryProvider
from binnair_trading_engine.predictor.interface import Predictor

logger = logging.getLogger(__name__)


class TimesFMPredictor(Predictor):
    """
    TimesFM zero-shot forecast 결과를 BUY/SELL/HOLD 신호로 변환한다.

    forecast_mode:
    - average: horizon 각 스텝 수익률의 산술 평균 → score
    - last: forecast_index 한 스텝만 사용 (legacy)

    expected_return(score)이 threshold보다 크면 BUY, 작으면 SELL, 나머지 HOLD.
    """

    def __init__(
        self,
        config: PredictorTimesFMConfig,
        price_history_provider: PriceHistoryProvider | None = None,
    ) -> None:
        self._config = config
        self._price_history: deque[float] = deque(maxlen=config.context_length)
        self._model: Any = None
        self._price_history_provider = price_history_provider
        self._price_history_provider_failed = False
        if config.signal_threshold is not None:
            self._threshold = float(config.signal_threshold)
        else:
            self._threshold = (
                config.fee_rate * 2.0
                + config.slippage_rate
                + config.safety_margin
            )
        logger.info(
            "TimesFM signal threshold: %.6f (%.4f%%), forecast_mode=%s",
            self._threshold,
            self._threshold * 100,
            config.forecast_mode or "average",
        )
        self._initial_threshold = self._threshold
        self._forecast_mode = (config.forecast_mode or "average").lower()
        if self._forecast_mode not in ("average", "last"):
            logger.warning(
                "Unknown forecast_mode=%r, using average",
                config.forecast_mode,
            )
            self._forecast_mode = "average"
        self._load_model()

    def _load_model(self) -> None:
        """TimesFM 사전학습 모델을 로드하고 추론 설정을 컴파일한다."""
        try:
            import timesfm

            if self._config.model_id != "google/timesfm-2.5-200m-pytorch":
                raise ValueError(
                    "현재 TimesFMPredictor는 "
                    "google/timesfm-2.5-200m-pytorch 로더만 지원합니다."
                )

            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                self._config.model_id
            )
            model.compile(
                timesfm.ForecastConfig(
                    max_context=self._config.context_length,
                    max_horizon=self._config.horizon,
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                    force_flip_invariance=True,
                    infer_is_positive=True,
                    fix_quantile_crossing=True,
                )
            )
            self._model = model
        except Exception as e:
            logger.warning("TimesFM model load failed, using HOLD fallback: %s", e)
            self._model = None

    def set_threshold(self, value: float) -> None:
        """Autopilot — 런타임 adaptive threshold."""
        if value > 0:
            self._threshold = float(value)

    def get_threshold(self) -> float:
        return self._threshold

    def get_initial_threshold(self) -> float:
        return getattr(self, "_initial_threshold", self._threshold)

    def predict(
        self,
        snapshot: MarketSnapshot,
        ctx: TradeContext,
    ) -> Prediction | None:
        self._price_history.append(float(snapshot.price))

        history = self._get_price_history(snapshot)
        if self._model is None or len(history) < self._config.min_context:
            return self._hold(snapshot)

        try:
            current_price = float(snapshot.price)
            history_arr = np.asarray(history, dtype=np.float32)
            point_forecast, _ = self._model.forecast(
                horizon=self._config.horizon,
                inputs=[history_arr],
            )
            forecast_prices = self._parse_forecast_prices(point_forecast)
            forecast_returns = self._step_returns(current_price, forecast_prices)
            expected_return = self._aggregate_return(forecast_returns)
            action = self._to_action(expected_return)
            confidence = self._to_confidence(expected_return)

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
            )
        except Exception as e:
            logger.exception("TimesFM inference failed: %s", e)
            return self._hold(snapshot)

    def _get_price_history(self, snapshot: MarketSnapshot) -> list[float]:
        if not self._config.use_ohlcv_history or self._price_history_provider is None:
            return list(self._price_history)

        closes = self._get_external_history(snapshot.symbol)
        if len(closes) >= self._config.min_context:
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

    def _to_action(self, expected_return: float) -> SignalAction:
        if expected_return > self._threshold:
            return SignalAction.BUY
        if expected_return < -self._threshold:
            return SignalAction.SELL
        return SignalAction.HOLD

    def _to_confidence(self, expected_return: float) -> float:
        if self._threshold <= 0:
            return 0.0
        return min(1.0, abs(expected_return) / self._threshold)

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

    def _hold(self, snapshot: MarketSnapshot) -> Prediction:
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
        )
