"""Binance REST API 시세 조회."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx

from binnair_trading_engine.domain.models import MarketSnapshot

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
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=str(uuid.uuid4()),
            )
        except httpx.HTTPError as e:
            logger.warning("Binance ticker fetch failed: %s", e)
            return None
        except (ValueError, TypeError) as e:
            logger.warning("Binance ticker parse error: %s", e)
            return None
