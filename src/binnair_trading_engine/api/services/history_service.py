"""
엔진 이력 API 서비스 — DB repository + 거래소 체결 보정.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from binnair_trading_engine.api.dto.history import (
    EngineHistorySummaryDTO,
    ExecutionHistoryItemDTO,
    OrderHistoryItemDTO,
)
from binnair_trading_engine.api.repositories.history_repository import EngineHistoryRepository
from binnair_trading_engine.api.services.order_fill_resolver import (
    enrich_order_fill_status,
    synthetic_execution_from_order,
)
from binnair_trading_engine.config.settings import EngineConfig
from binnair_trading_engine.exchange.interface import ExchangeAdapter

logger = logging.getLogger(__name__)


class HistoryService:
    """History repository + exchange fill reconciliation."""

    def __init__(
        self,
        repo: EngineHistoryRepository,
        config: EngineConfig | None = None,
    ) -> None:
        self._repo = repo
        self._exchange: ExchangeAdapter | None = None
        if config is not None and not config.exchange.paper_mode:
            try:
                from binnair_trading_engine.exchange import create_exchange

                self._exchange = create_exchange(config)
            except Exception as e:
                logger.warning("HistoryService: exchange unavailable: %s", e)

    def _enrich_orders(
        self, items: list[OrderHistoryItemDTO]
    ) -> list[OrderHistoryItemDTO]:
        return [enrich_order_fill_status(o, self._exchange) for o in items]

    def list_orders(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        side: str | None = None,
        fill_status: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
    ) -> list[OrderHistoryItemDTO]:
        raw = self._repo.list_orders(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            side=side,
            fill_status=None,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
        )
        items = self._enrich_orders(raw)
        if fill_status:
            items = [
                o for o in items if o.fill_status.upper() == fill_status.upper()
            ]
        return items

    def list_executions(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        side: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
    ) -> list[ExecutionHistoryItemDTO]:
        db_items = self._repo.list_executions(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            side=side,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
        )
        db_order_ids = {x.order_id for x in db_items}

        orders = self.list_orders(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            side=side,
            from_at=from_at,
            to_at=to_at,
            limit=min(limit, 200),
        )
        extras: list[ExecutionHistoryItemDTO] = []
        for o in orders:
            if o.order_id in db_order_ids:
                continue
            syn = synthetic_execution_from_order(o)
            if syn is not None:
                extras.append(syn)

        merged = db_items + extras
        merged.sort(key=lambda x: x.executed_at, reverse=True)
        return merged[:limit]

    def list_positions(self, **kwargs):
        return self._repo.list_positions(**kwargs)

    def list_trades(self, **kwargs):
        return self._repo.list_trades(**kwargs)

    def get_summary(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> EngineHistorySummaryDTO:
        base = self._repo.get_summary(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=from_at,
            to_at=to_at,
        )
        orders = self.list_orders(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=from_at,
            to_at=to_at,
            limit=500,
        )
        executions = self.list_executions(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=from_at,
            to_at=to_at,
            limit=500,
        )

        orders_filled = sum(
            1 for o in orders if o.fill_status in ("FILLED", "PARTIAL")
        )
        orders_pending = sum(1 for o in orders if o.fill_status == "PENDING")
        orders_missing = sum(1 for o in orders if o.execution_synced_from_exchange)

        return replace(
            base,
            orders_total=len(orders),
            orders_filled=orders_filled,
            orders_pending=orders_pending,
            orders_missing_db_execution=orders_missing,
            executions_total=len(executions),
        )
