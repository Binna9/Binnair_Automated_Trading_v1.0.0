"""
TimesFM 입력용 가격 히스토리 공급자를 정의한다.
ohlcv_candle DB의 최근 close 시계열을 Predictor에 전달한다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class PriceHistoryProvider(Protocol):
    """예측기에 최근 가격 히스토리를 제공하는 인터페이스."""

    def get_recent_prices(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[float]: ...

    def get_recent_ohlc(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[tuple[float, float, float]]: ...

    def get_latest_candle_open_time(
        self,
        symbol: str,
        timeframe: str,
    ) -> datetime | None: ...


class OhlcvDbPriceHistoryProvider:
    """ohlcv_candle 테이블의 close/OHLC 시계열을 제공한다."""

    def __init__(self) -> None:
        from binnair_trading_engine.infra.persistence.repositories.postgres import (
            PostgresRepositoryFactory,
        )

        self._repo = PostgresRepositoryFactory().ohlcv_candle

    def get_recent_prices(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[float]:
        return self._repo.get_recent_closes(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

    def get_recent_ohlc(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[tuple[float, float, float]]:
        """(high, low, close) 튜플, 오래된 순 — True Range ATR 계산용."""
        return self._repo.get_recent_ohlc(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

    def get_latest_candle_open_time(
        self,
        symbol: str,
        timeframe: str,
    ) -> datetime | None:
        return self._repo.get_latest_candle_open_time(
            symbol=symbol,
            timeframe=timeframe,
        )


def create_price_history_provider(config) -> PriceHistoryProvider | None:
    """설정에 따라 가격 히스토리 공급자를 생성한다."""
    if getattr(config, "predictor_type", "") != "timesfm":
        return None
    from binnair_trading_engine.config.settings import PredictorTimesFMConfig

    timesfm_config = (
        getattr(config, "predictor_timesfm_config", None)
        or PredictorTimesFMConfig()
    )
    if not timesfm_config or not getattr(timesfm_config, "use_ohlcv_history", False):
        return None
    if getattr(config.storage, "backend", "postgres") != "postgres":
        logger.info("OHLCV history disabled: storage backend is not postgres")
        return None
    return OhlcvDbPriceHistoryProvider()
