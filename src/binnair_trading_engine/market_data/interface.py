"""시세 수신 인터페이스."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from binnair_trading_engine.domain.models import MarketSnapshot


class MarketDataProvider(Protocol):
    """시세 제공자. REST 폴링 / WebSocket 구독 등."""

    def fetch_snapshot(self, symbol: str, run_id: str = "") -> MarketSnapshot | None:
        """
        현재 시세 조회.
        Returns:
            MarketSnapshot or None (조회 실패 시)
        """
        ...
