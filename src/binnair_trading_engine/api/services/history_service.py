"""
엔진 이력 API 서비스 — DB repository + 거래소 체결 보정.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from binnair_trading_engine.api.dto.history import (
    EngineHistorySummaryDTO,
    EquityHistoryItemDTO,
    ExecutionHistoryItemDTO,
    OrderHistoryItemDTO,
    PositionHistoryItemDTO,
    TickDetailDTO,
    TradeHistoryItemDTO,
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
        offset: int = 0,
    ) -> tuple[list[OrderHistoryItemDTO], int]:
        # DB fill_status 필터는 조인 기준. exchange reconcile 후 재필터할 수 있어
        # PENDING/FILLED는 페이지 후 메모리 필터(total은 DB 기준).
        raw, total = self._repo.list_orders(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            side=side,
            fill_status=fill_status,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )
        items = self._enrich_orders(raw)
        if fill_status:
            want = fill_status.upper()
            items = [o for o in items if o.fill_status.upper() == want]
        return items, total

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
        offset: int = 0,
    ) -> tuple[list[ExecutionHistoryItemDTO], int]:
        db_items, total = self._repo.list_executions(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            side=side,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )
        # offset=0 첫 페이지만 거래소 합성 체결을 앞에 병합 (페이지 일관성 유지)
        if offset == 0 and self._exchange is not None:
            db_order_ids = {x.order_id for x in db_items}
            orders, _ = self.list_orders(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                side=side,
                from_at=from_at,
                to_at=to_at,
                limit=min(limit, 200),
                offset=0,
            )
            extras: list[ExecutionHistoryItemDTO] = []
            for o in orders:
                if o.order_id in db_order_ids:
                    continue
                syn = synthetic_execution_from_order(o)
                if syn is not None:
                    extras.append(syn)
            if extras:
                merged = extras + db_items
                merged.sort(key=lambda x: x.executed_at, reverse=True)
                return merged[:limit], total + len(extras)
        return db_items, total

    def list_positions(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        open_only_latest: bool = False,
    ) -> tuple[list[PositionHistoryItemDTO], int]:
        return self._repo.list_positions(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            status=status,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
            open_only_latest=open_only_latest,
        )

    def list_trades(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        exit_reason: str | None = None,
        is_win: bool | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[TradeHistoryItemDTO], int]:
        return self._repo.list_trades(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            exit_reason=exit_reason,
            is_win=is_win,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )

    def list_equity(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[EquityHistoryItemDTO], int]:
        return self._repo.list_equity(
            user_id=user_id,
            run_id=run_id,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )

    def get_tick_detail(
        self,
        *,
        correlation_id: str,
        user_id: str = "default",
    ) -> TickDetailDTO:
        return self._repo.get_tick_detail(
            correlation_id=correlation_id,
            user_id=user_id,
        )

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
        # 거래소 보정으로 DB에 없는 체결이 있는 주문 수 (샘플 상한)
        if self._exchange is None:
            return base
        orders, _ = self.list_orders(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=from_at,
            to_at=to_at,
            limit=200,
            offset=0,
        )
        missing = sum(1 for o in orders if o.execution_synced_from_exchange)
        return replace(base, orders_missing_db_execution=missing)
