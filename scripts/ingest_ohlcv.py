#!/usr/bin/env python3
"""
Binance OHLCV 캔들을 가져와 ohlcv_candle 테이블에 저장한다.

일회성 백필:
  CONFIG_PATH=config/config.yaml python scripts/ingest_ohlcv.py --symbol BTCUSDT --timeframe 1m --limit 500

상시 적재:
  CONFIG_PATH=config/config.yaml python scripts/ingest_ohlcv.py --symbol BTCUSDT --timeframe 1m --limit 2 --loop
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.infra.persistence.dto import OhlcvCandleCreate
from binnair_trading_engine.infra.persistence.repositories.postgres import (
    PostgresRepositoryFactory,
)
from binnair_trading_engine.market_data.binance_rest import BinanceRestMarketData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logger = logging.getLogger("ingest_ohlcv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Binance OHLCV and store it.")
    parser.add_argument("--symbol", default="BTCUSDT", help="Binance symbol.")
    parser.add_argument("--timeframe", default="1m", help="Binance kline interval.")
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of candles to fetch per request. Binance max is usually 1000.",
    )
    parser.add_argument("--base-url", default="https://api.binance.com")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep fetching and upserting candles until interrupted.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=60.0,
        help="Seconds between fetches when --loop is enabled.",
    )
    return parser.parse_args()


def ingest_once(
    provider: BinanceRestMarketData,
    repos: PostgresRepositoryFactory,
    symbol: str,
    timeframe: str,
    limit: int,
) -> int:
    candles = provider.fetch_klines(symbol=symbol, interval=timeframe, limit=limit)
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
    affected = repos.ohlcv_candle.upsert_many(dtos)
    logger.info(
        "OHLCV upsert complete: symbol=%s timeframe=%s fetched=%d affected=%d",
        symbol,
        timeframe,
        len(candles),
        affected,
    )
    return affected


def main() -> int:
    args = parse_args()
    provider = BinanceRestMarketData(base_url=args.base_url, timeout=args.timeout)
    repos = PostgresRepositoryFactory()

    if not args.loop:
        ingest_once(provider, repos, args.symbol, args.timeframe, args.limit)
        return 0

    logger.info(
        "Starting OHLCV ingestion loop: symbol=%s timeframe=%s interval=%.1fs",
        args.symbol,
        args.timeframe,
        args.poll_interval,
    )
    try:
        while True:
            ingest_once(provider, repos, args.symbol, args.timeframe, args.limit)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        logger.info("OHLCV ingestion stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
