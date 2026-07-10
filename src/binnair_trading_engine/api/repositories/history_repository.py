"""
엔진 DB 이력 조회 — 주문·체결·포지션·청산 거래.

FlowQueryRepository(타임라인/대시보드)와 분리해
프론트 "내역" 화면에 맞춘 flat 목록 + 요약을 제공한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, text

from binnair_trading_engine.api.common.db import get_db_session
from binnair_trading_engine.api.dto.history import (
    EngineHistorySummaryDTO,
    ExecutionHistoryItemDTO,
    OrderHistoryItemDTO,
    PositionHistoryItemDTO,
    TradeHistoryItemDTO,
)
from binnair_trading_engine.api.common.mappers import to_trade_result_dto
from binnair_trading_engine.infra.persistence.models import (
    EngineRunModel,
    OrderExecutionModel,
    OrderRequestModel,
    PositionSnapshotModel,
    SignalEventModel,
    TradeResultModel,
)


def _clamp_limit(limit: int, *, lo: int = 1, hi: int = 500) -> int:
    return max(lo, min(limit, hi))


class EngineHistoryRepository:
    """엔진 persistence 이력 read-only."""

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
        session = get_db_session()
        try:
            stmt = (
                select(OrderRequestModel)
                .where(OrderRequestModel.user_id == user_id)
                .order_by(OrderRequestModel.requested_at.desc())
                .limit(_clamp_limit(limit, hi=200))
            )
            if run_id:
                stmt = stmt.where(OrderRequestModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(OrderRequestModel.symbol == symbol)
            if side:
                stmt = stmt.where(OrderRequestModel.side == side.upper())
            if from_at:
                stmt = stmt.where(OrderRequestModel.requested_at >= from_at)
            if to_at:
                stmt = stmt.where(OrderRequestModel.requested_at < to_at)

            requests = session.execute(stmt).scalars().all()
            out: list[OrderHistoryItemDTO] = []
            for req in requests:
                exec_row = session.execute(
                    select(OrderExecutionModel)
                    .where(OrderExecutionModel.order_request_id == req.id)
                    .order_by(OrderExecutionModel.executed_at.desc())
                    .limit(1)
                ).scalars().first()
                item = _order_history_item(req, exec_row)
                if fill_status and item.fill_status.upper() != fill_status.upper():
                    continue
                out.append(item)
            return out
        finally:
            session.close()

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
        session = get_db_session()
        try:
            stmt = (
                select(OrderExecutionModel, OrderRequestModel)
                .outerjoin(
                    OrderRequestModel,
                    OrderExecutionModel.order_request_id == OrderRequestModel.id,
                )
                .where(OrderExecutionModel.user_id == user_id)
                .order_by(OrderExecutionModel.executed_at.desc())
                .limit(_clamp_limit(limit))
            )
            if run_id:
                stmt = stmt.where(OrderExecutionModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(OrderExecutionModel.symbol == symbol)
            if side:
                stmt = stmt.where(OrderRequestModel.side == side.upper())
            if from_at:
                stmt = stmt.where(OrderExecutionModel.executed_at >= from_at)
            if to_at:
                stmt = stmt.where(OrderExecutionModel.executed_at < to_at)

            rows = session.execute(stmt).all()
            items: list[ExecutionHistoryItemDTO] = []
            for ex, req in rows:
                order_type = req.order_type if req else None
                side_val = req.side if req else "UNKNOWN"
                corr = req.correlation_id if req else ""
                requested_at = req.requested_at if req else None
                price = ex.executed_price
                notional = (
                    float(price) * float(ex.executed_quantity)
                    if price is not None
                    else None
                )
                items.append(
                    ExecutionHistoryItemDTO(
                        id=ex.id,
                        order_request_id=ex.order_request_id,
                        run_id=ex.run_id,
                        symbol=ex.symbol,
                        side=side_val,
                        order_type=order_type,
                        order_id=ex.order_id,
                        status=ex.status,
                        executed_qty=ex.executed_quantity,
                        executed_price=ex.executed_price,
                        notional_usdt=notional,
                        reduce_only=ex.reduce_only,
                        position_side=ex.position_side,
                        correlation_id=corr or "",
                        paper_mode=ex.paper_mode,
                        requested_at=requested_at,
                        executed_at=ex.executed_at,
                    )
                )
            return items
        finally:
            session.close()

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
        open_only_latest: bool = False,
    ) -> list[PositionHistoryItemDTO]:
        """
        포지션 스냅샷 이력.
        open_only_latest=True 이면 심볼별 최신 OPEN 1건만 (현재 보유).
        """
        session = get_db_session()
        try:
            if open_only_latest and (status or "OPEN").upper() == "OPEN":
                schema = PositionSnapshotModel.__table__.schema or "trade"
                sql = f"""
                    SELECT id FROM (
                        SELECT DISTINCT ON (symbol) id, status, quantity
                        FROM "{schema}".position_snapshot
                        WHERE user_id = :user_id
                """
                params: dict = {"user_id": user_id}
                if run_id:
                    sql += " AND run_id = :run_id"
                    params["run_id"] = run_id
                if symbol:
                    sql += " AND symbol = :symbol"
                    params["symbol"] = symbol
                sql += """
                        ORDER BY symbol, snapshot_at DESC
                    ) latest
                    WHERE latest.status = 'OPEN' AND latest.quantity > 0
                """
                id_rows = session.execute(text(sql), params).all()
                ids = [r[0] for r in id_rows]
                if not ids:
                    return []
                rows = session.execute(
                    select(PositionSnapshotModel).where(PositionSnapshotModel.id.in_(ids))
                ).scalars().all()
                by_id = {r.id: r for r in rows}
                return [_position_history_item(by_id[i]) for i in ids if i in by_id]

            stmt = (
                select(PositionSnapshotModel)
                .where(PositionSnapshotModel.user_id == user_id)
                .order_by(PositionSnapshotModel.snapshot_at.desc())
                .limit(_clamp_limit(limit))
            )
            if run_id:
                stmt = stmt.where(PositionSnapshotModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(PositionSnapshotModel.symbol == symbol)
            if status:
                stmt = stmt.where(PositionSnapshotModel.status == status.upper())
            if from_at:
                stmt = stmt.where(PositionSnapshotModel.snapshot_at >= from_at)
            if to_at:
                stmt = stmt.where(PositionSnapshotModel.snapshot_at < to_at)

            rows = session.execute(stmt).scalars().all()
            return [_position_history_item(r) for r in rows]
        finally:
            session.close()

    def list_trades(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
    ) -> list[TradeHistoryItemDTO]:
        """청산 완료 라운드트rip — trade_result."""
        session = get_db_session()
        try:
            stmt = (
                select(TradeResultModel)
                .where(TradeResultModel.user_id == user_id)
                .order_by(TradeResultModel.closed_at.desc())
                .limit(_clamp_limit(limit))
            )
            if run_id:
                stmt = stmt.where(TradeResultModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(TradeResultModel.symbol == symbol)
            if from_at:
                stmt = stmt.where(TradeResultModel.closed_at >= from_at)
            if to_at:
                stmt = stmt.where(TradeResultModel.closed_at < to_at)

            rows = session.execute(stmt).scalars().all()
            items: list[TradeHistoryItemDTO] = []
            for row in rows:
                dto = to_trade_result_dto(row)
                holding = None
                if dto.opened_at and dto.closed_at:
                    holding = (dto.closed_at - dto.opened_at).total_seconds()
                items.append(
                    TradeHistoryItemDTO(
                        trade_id=dto.trade_id,
                        run_id=dto.run_id,
                        symbol=dto.symbol,
                        side=dto.side,
                        quantity=dto.quantity,
                        entry_price=dto.entry_price,
                        exit_price=dto.exit_price,
                        realized_pnl=dto.realized_pnl,
                        pnl_pct=dto.pnl_pct,
                        is_win=dto.is_win,
                        exit_reason=dto.exit_reason,
                        opened_at=dto.opened_at,
                        closed_at=dto.closed_at,
                        paper_mode=dto.paper_mode,
                        holding_seconds=holding,
                    )
                )
            return items
        finally:
            session.close()

    def get_summary(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> EngineHistorySummaryDTO:
        session = get_db_session()
        try:
            engine_status = None
            if run_id:
                run_row = session.execute(
                    select(EngineRunModel).where(
                        EngineRunModel.run_id == run_id,
                        EngineRunModel.user_id == user_id,
                    )
                ).scalars().first()
                if run_row:
                    engine_status = run_row.status

            open_positions = len(
                self.list_positions(
                    user_id=user_id,
                    run_id=run_id,
                    symbol=symbol,
                    open_only_latest=True,
                )
            )

            orders = self.list_orders(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
                limit=500,
            )
            orders_filled = sum(1 for o in orders if o.fill_status == "FILLED")
            orders_pending = sum(1 for o in orders if o.fill_status == "PENDING")

            executions = self.list_executions(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
                limit=500,
            )

            closed_positions = len(
                self.list_positions(
                    user_id=user_id,
                    run_id=run_id,
                    symbol=symbol,
                    status="CLOSED",
                    from_at=from_at,
                    to_at=to_at,
                    limit=500,
                )
            )

            trades = self.list_trades(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
                limit=500,
            )
            realized_sum = sum(t.realized_pnl for t in trades)

            latest_signal = _latest_at(
                session,
                SignalEventModel,
                SignalEventModel.event_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )
            latest_order = _latest_at(
                session,
                OrderRequestModel,
                OrderRequestModel.requested_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )
            latest_exec = _latest_at(
                session,
                OrderExecutionModel,
                OrderExecutionModel.executed_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )
            latest_pos = _latest_at(
                session,
                PositionSnapshotModel,
                PositionSnapshotModel.snapshot_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )

            return EngineHistorySummaryDTO(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                engine_status=engine_status,
                open_positions=open_positions,
                orders_total=len(orders),
                orders_filled=orders_filled,
                orders_pending=orders_pending,
                orders_missing_db_execution=0,
                executions_total=len(executions),
                closed_positions=closed_positions,
                closed_trades=len(trades),
                realized_pnl_sum=realized_sum,
                latest_signal_at=latest_signal,
                latest_order_at=latest_order,
                latest_execution_at=latest_exec,
                latest_position_at=latest_pos,
                filters={
                    "from_at": from_at.isoformat() if from_at else None,
                    "to_at": to_at.isoformat() if to_at else None,
                },
            )
        finally:
            session.close()


def _order_history_item(
    req: OrderRequestModel,
    ex: OrderExecutionModel | None,
) -> OrderHistoryItemDTO:
    fill_status = _derive_fill_status(req, ex)
    return OrderHistoryItemDTO(
        id=req.id,
        run_id=req.run_id,
        symbol=req.symbol,
        side=req.side,
        order_type=req.order_type,
        quantity=req.quantity,
        requested_price=req.price,
        requested_at=req.requested_at,
        order_id=req.order_id,
        client_order_id=req.client_order_id,
        reduce_only=req.reduce_only,
        position_side=req.position_side,
        correlation_id=req.correlation_id or "",
        paper_mode=req.paper_mode,
        fill_status=fill_status,
        filled_qty=ex.executed_quantity if ex else None,
        avg_fill_price=ex.executed_price if ex else None,
        executed_at=ex.executed_at if ex else None,
        execution_id=ex.id if ex else None,
    )


def _derive_fill_status(
    req: OrderRequestModel,
    ex: OrderExecutionModel | None,
) -> str:
    if ex is not None:
        return ex.status or "FILLED"
    if req.order_id:
        return "PENDING"
    return "REJECTED"


def _position_history_item(row: PositionSnapshotModel) -> PositionHistoryItemDTO:
    duration = None
    if row.opened_at and row.closed_at:
        duration = (row.closed_at - row.opened_at).total_seconds()
    return PositionHistoryItemDTO(
        id=row.id,
        run_id=row.run_id,
        symbol=row.symbol,
        side=row.side,
        status=row.status,
        quantity=row.quantity,
        avg_entry_price=row.avg_entry_price,
        tp_price=row.tp_price,
        sl_price=row.sl_price,
        unrealized_pnl=row.unrealized_pnl,
        realized_pnl=row.realized_pnl,
        exit_reason=row.exit_reason,
        exit_price=row.exit_price,
        opened_at=row.opened_at,
        closed_at=row.closed_at,
        snapshot_at=row.snapshot_at,
        paper_mode=row.paper_mode,
        duration_seconds=duration,
    )


def _latest_at(
    session,
    model,
    ts_col,
    user_id: str,
    run_id: str | None,
    symbol: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> datetime | None:
    stmt = select(func.max(ts_col)).where(model.user_id == user_id)
    if run_id and hasattr(model, "run_id"):
        stmt = stmt.where(model.run_id == run_id)
    if symbol and hasattr(model, "symbol"):
        stmt = stmt.where(model.symbol == symbol)
    if from_at:
        stmt = stmt.where(ts_col >= from_at)
    if to_at:
        stmt = stmt.where(ts_col < to_at)
    val = session.execute(stmt).scalar()
    return val
