"""
Binance 공개 REST API로 시세와 klines를 조회한다.
ticker snapshot과 OHLCV 캔들 도메인 객체를 생성한다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from binnair_trading_engine.infra.timezone import now_kst

import httpx

from binnair_trading_engine.domain.models import MarketSnapshot, OhlcvCandle

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.binance.com"


class BinanceRestMarketData:
    """
    Binance Spot REST API로 시세 조회.
    GET /api/v3/ticker/price (공개, API 키 불필요)
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def fetch_snapshot(self, symbol: str, run_id: str = "") -> MarketSnapshot | None:
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/ticker/price",
                params={"symbol": symbol},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            price_str = data.get("price")
            if price_str is None:
                logger.warning("Binance ticker price missing: %s", data)
                return None
            price = float(price_str)
            return MarketSnapshot(
                symbol=symbol,
                price=price,
                timestamp=now_kst(),
                run_id=run_id,
                correlation_id=str(uuid.uuid4()),
            )
        except httpx.HTTPError as e:
            logger.warning("Binance ticker fetch failed: %s", e)
            return None
        except (ValueError, TypeError) as e:
            logger.warning("Binance ticker parse error: %s", e)
            return None

    def fetch_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 500,
    ) -> list[OhlcvCandle]:
        """Binance Spot REST API에서 OHLCV 캔들을 조회한다."""
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return [
                self._parse_kline(symbol=symbol, interval=interval, row=row)
                for row in resp.json()
            ]
        except httpx.HTTPError as e:
            logger.warning("Binance kline fetch failed: %s", e)
            return []
        except (ValueError, TypeError, IndexError) as e:
            logger.warning("Binance kline parse error: %s", e)
            return []

    def _parse_kline(
        self,
        symbol: str,
        interval: str,
        row: list,
    ) -> OhlcvCandle:
        return OhlcvCandle(
            symbol=symbol,
            timeframe=interval,
            open_time=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            close_time=datetime.fromtimestamp(row[6] / 1000, tz=timezone.utc),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            quote_volume=float(row[7]) if row[7] is not None else None,
            trade_count=int(row[8]) if row[8] is not None else None,
        )
