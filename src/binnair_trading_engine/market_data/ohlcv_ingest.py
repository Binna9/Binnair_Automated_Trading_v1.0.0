"""
Binance OHLCV 캔들을 조회해 ohlcv_candle 테이블에 upsert한다.
scripts/ingest_ohlcv.py CLI가 호출하는 공통 적재 로직이다.
"""
from __future__ import annotations

import logging
import time
from threading import Event

from binnair_trading_engine.infra.persistence.dto import OhlcvCandleCreate
from binnair_trading_engine.infra.persistence.repositories.postgres import (
    PostgresRepositoryFactory,
)
from binnair_trading_engine.market_data.binance_rest import BinanceRestMarketData

logger = logging.getLogger(__name__)


def ingest_ohlcv_once(
    *,
    symbol: str,
    timeframe: str,
    limit: int,
    base_url: str = "https://api.binance.com",
    timeout: float = 10.0,
    provider: BinanceRestMarketData | None = None,
    repos: PostgresRepositoryFactory | None = None,
) -> int:
    """최근 OHLCV 캔들을 Binance에서 가져와 DB에 upsert한다."""
    market = provider or BinanceRestMarketData(base_url=base_url, timeout=timeout)
    repository_factory = repos or PostgresRepositoryFactory()
    candles = market.fetch_klines(symbol=symbol, interval=timeframe, limit=limit)
    dtos = [
        OhlcvCandleCreate(
            symbol=c.symbol,
            timeframe=c.timeframe,
            open_time=c.open_time,
            close_time=c.close_time,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            quote_volume=c.quote_volume,
            trade_count=c.trade_count,
        )
        for c in candles
    ]
    affected = repository_factory.ohlcv_candle.upsert_many(dtos)
    logger.info(
        "OHLCV upsert complete: symbol=%s timeframe=%s fetched=%d affected=%d",
        symbol,
        timeframe,
        len(candles),
        affected,
    )
    return affected


def run_ohlcv_ingest_loop(
    *,
    symbol: str,
    timeframe: str,
    limit: int,
    poll_interval: float,
    base_url: str = "https://api.binance.com",
    timeout: float = 10.0,
    stop_event: Event | None = None,
) -> None:
    """주기적으로 OHLCV를 적재한다. stop_event가 set되면 종료한다."""
    provider = BinanceRestMarketData(base_url=base_url, timeout=timeout)
    repos = PostgresRepositoryFactory()
    logger.info(
        "Starting OHLCV ingestion loop: symbol=%s timeframe=%s interval=%.1fs",
        symbol,
        timeframe,
        poll_interval,
    )
    while True:
        ingest_ohlcv_once(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            provider=provider,
            repos=repos,
        )
        if stop_event is None:
            time.sleep(poll_interval)
            continue
        if stop_event.wait(timeout=poll_interval):
            break
    logger.info("OHLCV ingestion loop stopped")
