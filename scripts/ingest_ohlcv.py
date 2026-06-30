#!/usr/bin/env python3
"""
Binance OHLCV 캔들을 조회해 ohlcv_candle 테이블에 upsert한다.
TimesFM 입력 히스토리를 백필하거나 상시 적재하는 운영 스크립트다.

보통은 run_engine.py가 이 스크립트를 subprocess로 호출한다.
단독 실행 예:
  CONFIG_PATH=config/config.yaml .venv/bin/python scripts/ingest_ohlcv.py --loop
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.market_data.ohlcv_ingest import (
    ingest_ohlcv_once,
    run_ohlcv_ingest_loop,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logger = logging.getLogger("ingest_ohlcv")


def _ensure_config_path() -> None:
    if os.environ.get("CONFIG_PATH"):
        return
    default_config = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    if default_config.exists():
        os.environ["CONFIG_PATH"] = str(default_config)


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


def main() -> int:
    _ensure_config_path()
    args = parse_args()

    if not args.loop:
        ingest_ohlcv_once(
            symbol=args.symbol,
            timeframe=args.timeframe,
            limit=args.limit,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        return 0

    try:
        run_ohlcv_ingest_loop(
            symbol=args.symbol,
            timeframe=args.timeframe,
            limit=args.limit,
            poll_interval=args.poll_interval,
            base_url=args.base_url,
            timeout=args.timeout,
        )
    except KeyboardInterrupt:
        logger.info("OHLCV ingestion stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
