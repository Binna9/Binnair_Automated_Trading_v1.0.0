"""
엔진 매매 이력 API 응답 DTO.

프론트 화면(주문 내역 / 체결 내역 / 포지션 내역 / 청산 거래) 단위로 필드 정리.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class OrderHistoryItemDTO:
    """주문 요청 1건 + 체결 요약."""

    id: int
    run_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    requested_price: float | None
    requested_at: datetime
    order_id: str | None
    client_order_id: str | None
    reduce_only: bool
    position_side: str
    correlation_id: str
    paper_mode: bool
    # derived from order_execution
    fill_status: str  # PENDING | FILLED | REJECTED | CANCELLED | UNKNOWN
    filled_qty: float | None = None
    avg_fill_price: float | None = None
    executed_at: datetime | None = None
    execution_id: int | None = None


@dataclass
class ExecutionHistoryItemDTO:
    """체결( fill ) 1건 — order_execution 기준."""

    id: int
    order_request_id: int | None
    run_id: str
    symbol: str
    side: str
    order_type: str | None
    order_id: str
    status: str
    executed_qty: float
    executed_price: float | None
    notional_usdt: float | None
    reduce_only: bool
    position_side: str
    correlation_id: str
    paper_mode: bool
    requested_at: datetime | None
    executed_at: datetime


@dataclass
class PositionHistoryItemDTO:
    """포지션 스냅샷 1건 (OPEN 진입 또는 CLOSED 청산)."""

    id: int
    run_id: str
    symbol: str
    side: str | None
    status: str | None
    quantity: float
    avg_entry_price: float
    tp_price: float | None
    sl_price: float | None
    unrealized_pnl: float
    realized_pnl: float | None
    exit_reason: str | None
    exit_price: float | None
    opened_at: datetime | None
    closed_at: datetime | None
    snapshot_at: datetime
    paper_mode: bool
    duration_seconds: float | None = None


@dataclass
class TradeHistoryItemDTO:
    """청산 완료 거래 1건 — trade_result (라운드트립)."""

    trade_id: str
    run_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    realized_pnl: float
    pnl_pct: float | None
    exit_reason: str | None
    opened_at: datetime
    closed_at: datetime
    paper_mode: bool
    holding_seconds: float | None = None


@dataclass
class EngineHistorySummaryDTO:
    """현재 run(또는 필터) 기준 이력 요약."""

    user_id: str
    run_id: str | None
    symbol: str | None
    engine_status: str | None
    open_positions: int
    orders_total: int
    orders_filled: int
    orders_pending: int
    executions_total: int
    closed_positions: int
    closed_trades: int
    realized_pnl_sum: float
    latest_signal_at: datetime | None
    latest_order_at: datetime | None
    latest_execution_at: datetime | None
    latest_position_at: datetime | None
    filters: dict[str, Any] = field(default_factory=dict)
