"""
주문 체결 상태 보정 — DB order_execution 누락 시 거래소 조회.

order_id는 있는데 execution 행이 없으면 (과거 fill sync 버그)
API가 PENDING/미체결 1건으로 잘못 집계되는 문제를 해결한다.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta

from binnair_trading_engine.api.dto.history import (
    ExecutionHistoryItemDTO,
    OrderHistoryItemDTO,
)
from binnair_trading_engine.domain.models import OrderStatus
from binnair_trading_engine.exchange.interface import ExchangeAdapter
from binnair_trading_engine.infra.timezone import ensure_kst, now_kst

logger = logging.getLogger(__name__)

# MARKET 주문은 수 분 내 체결되어야 함 — 그 이후 PENDING 유지는 오류 데이터로 간주
_STALE_MARKET_AFTER = timedelta(minutes=10)


def _exchange_fill_status(status: OrderStatus) -> str:
    if status == OrderStatus.FILLED:
        return "FILLED"
    if status == OrderStatus.PARTIALLY_FILLED:
        return "PARTIAL"
    if status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
        return status.value
    if status in (OrderStatus.SUBMITTED, OrderStatus.PENDING):
        return "PENDING"
    return status.value.upper()


def enrich_order_fill_status(
    item: OrderHistoryItemDTO,
    exchange: ExchangeAdapter | None,
) -> OrderHistoryItemDTO:
    """DB execution 없이 order_id만 있는 주문 — 거래소 상태로 보정."""
    if item.execution_id is not None:
        return item
    if not item.order_id:
        return item

    if exchange is not None:
        try:
            ex_order = exchange.get_order(item.symbol, item.order_id)
        except Exception as e:
            logger.debug("exchange get_order failed for %s: %s", item.order_id, e)
            ex_order = None

        if ex_order is not None:
            fill_status = _exchange_fill_status(ex_order.status)
            filled_qty = ex_order.quantity if ex_order.quantity > 0 else None
            avg_price = ex_order.price if ex_order.price and ex_order.price > 0 else None
            notional = (
                float(avg_price) * float(filled_qty)
                if avg_price is not None and filled_qty
                else None
            )
            return replace(
                item,
                fill_status=fill_status,
                filled_qty=filled_qty,
                avg_fill_price=avg_price,
                executed_at=item.executed_at,
                execution_synced_from_exchange=item.execution_id is None
                and fill_status == "FILLED",
                exchange_status=ex_order.status.value,
                notional_usdt=notional,
            )

    requested_at = ensure_kst(item.requested_at)
    age = now_kst() - requested_at
    if item.order_type.upper() == "MARKET" and age > _STALE_MARKET_AFTER:
        return replace(
            item,
            fill_status="UNKNOWN",
            execution_synced_from_exchange=False,
        )

    return item


def synthetic_execution_from_order(
    item: OrderHistoryItemDTO,
) -> ExecutionHistoryItemDTO | None:
    """DB execution 행 없이 거래소에서 FILLED 확인된 주문 → 체결 DTO."""
    if item.fill_status != "FILLED" or not item.order_id or item.execution_id:
        return None
    if not item.execution_synced_from_exchange:
        return None

    price = item.avg_fill_price
    qty = item.filled_qty or item.quantity
    notional = item.notional_usdt
    if notional is None and price is not None:
        notional = float(price) * float(qty)

    return ExecutionHistoryItemDTO(
        id=-item.id,
        order_request_id=item.id,
        run_id=item.run_id,
        symbol=item.symbol,
        side=item.side,
        order_type=item.order_type,
        order_id=item.order_id,
        status="FILLED",
        executed_qty=qty,
        executed_price=price,
        notional_usdt=notional,
        reduce_only=item.reduce_only,
        position_side=item.position_side,
        correlation_id=item.correlation_id,
        paper_mode=item.paper_mode,
        requested_at=item.requested_at,
        executed_at=item.executed_at or item.requested_at,
        synced_from_exchange=True,
    )
