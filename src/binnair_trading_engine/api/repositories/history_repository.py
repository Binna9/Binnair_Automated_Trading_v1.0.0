"""
엔진 DB 이력 조회 — 주문·체결·포지션·청산 거래·잔고·틱 상세.

FlowQueryRepository(타임라인/대시보드)와 분리해
프론트 "내역" 화면에 맞춘 flat 목록 + 요약을 제공한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import aliased

from binnair_trading_engine.api.common.db import get_db_session
from binnair_trading_engine.api.common.mappers import (
    to_audit_log_dto,
    to_model_inference_dto,
    to_order_execution_dto,
    to_order_request_dto,
    to_position_snapshot_dto,
    to_signal_event_dto,
    to_trade_result_dto,
)
from binnair_trading_engine.api.common.page import clamp_limit, clamp_offset
from binnair_trading_engine.api.common.serialize import serialize
from binnair_trading_engine.api.dto.history import (
    EngineHistorySummaryDTO,
    EquityHistoryItemDTO,
    ExecutionHistoryItemDTO,
    OrderHistoryItemDTO,
    PositionHistoryItemDTO,
    TickDetailDTO,
    TradeHistoryItemDTO,
)
from binnair_trading_engine.infra.persistence.models import (
    AuditLogModel,
    EngineRunModel,
    EquitySnapshotModel,
    ModelInferenceEventModel,
    OrderExecutionModel,
    OrderRequestModel,
    PositionSnapshotModel,
    SignalEventModel,
    TradeResultModel,
)


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
        offset: int = 0,
    ) -> tuple[list[OrderHistoryItemDTO], int]:
        session = get_db_session()
        try:
            lim = clamp_limit(limit, hi=200)
            off = clamp_offset(offset)
            LatestExec = aliased(OrderExecutionModel)

            latest_exec_sq = (
                select(
                    OrderExecutionModel.order_request_id.label("order_request_id"),
                    func.max(OrderExecutionModel.id).label("max_id"),
                )
                .where(OrderExecutionModel.user_id == user_id)
                .group_by(OrderExecutionModel.order_request_id)
                .subquery()
            )

            stmt = (
                select(OrderRequestModel, LatestExec)
                .outerjoin(
                    latest_exec_sq,
                    latest_exec_sq.c.order_request_id == OrderRequestModel.id,
                )
                .outerjoin(
                    LatestExec,
                    LatestExec.id == latest_exec_sq.c.max_id,
                )
                .where(OrderRequestModel.user_id == user_id)
            )
            count_stmt = select(func.count()).select_from(OrderRequestModel).where(
                OrderRequestModel.user_id == user_id
            )

            def _apply_filters(s):
                if run_id:
                    s = s.where(OrderRequestModel.run_id == run_id)
                if symbol:
                    s = s.where(OrderRequestModel.symbol == symbol)
                if side:
                    s = s.where(OrderRequestModel.side == side.upper())
                if from_at:
                    s = s.where(OrderRequestModel.requested_at >= from_at)
                if to_at:
                    s = s.where(OrderRequestModel.requested_at < to_at)
                return s

            stmt = _apply_filters(stmt)
            count_stmt = _apply_filters(count_stmt)

            if fill_status:
                fs = fill_status.upper()
                if fs == "PENDING":
                    cond = and_(
                        OrderRequestModel.order_id.is_not(None),
                        LatestExec.id.is_(None),
                    )
                elif fs == "REJECTED":
                    cond = and_(
                        OrderRequestModel.order_id.is_(None),
                        LatestExec.id.is_(None),
                    )
                else:
                    cond = LatestExec.status == fs
                # count needs same join for fill_status
                count_stmt = (
                    select(func.count())
                    .select_from(OrderRequestModel)
                    .outerjoin(
                        latest_exec_sq,
                        latest_exec_sq.c.order_request_id == OrderRequestModel.id,
                    )
                    .outerjoin(LatestExec, LatestExec.id == latest_exec_sq.c.max_id)
                    .where(OrderRequestModel.user_id == user_id)
                )
                count_stmt = _apply_filters(count_stmt).where(cond)
                stmt = stmt.where(cond)

            total = int(session.execute(count_stmt).scalar() or 0)
            rows = session.execute(
                stmt.order_by(OrderRequestModel.requested_at.desc())
                .offset(off)
                .limit(lim)
            ).all()
            return [_order_history_item(req, ex) for req, ex in rows], total
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
        offset: int = 0,
    ) -> tuple[list[ExecutionHistoryItemDTO], int]:
        session = get_db_session()
        try:
            lim = clamp_limit(limit)
            off = clamp_offset(offset)
            base = (
                select(OrderExecutionModel, OrderRequestModel)
                .outerjoin(
                    OrderRequestModel,
                    OrderExecutionModel.order_request_id == OrderRequestModel.id,
                )
                .where(OrderExecutionModel.user_id == user_id)
            )
            count_stmt = (
                select(func.count())
                .select_from(OrderExecutionModel)
                .outerjoin(
                    OrderRequestModel,
                    OrderExecutionModel.order_request_id == OrderRequestModel.id,
                )
                .where(OrderExecutionModel.user_id == user_id)
            )

            def _apply(s):
                if run_id:
                    s = s.where(OrderExecutionModel.run_id == run_id)
                if symbol:
                    s = s.where(OrderExecutionModel.symbol == symbol)
                if side:
                    s = s.where(OrderRequestModel.side == side.upper())
                if from_at:
                    s = s.where(OrderExecutionModel.executed_at >= from_at)
                if to_at:
                    s = s.where(OrderExecutionModel.executed_at < to_at)
                return s

            base = _apply(base)
            total = int(session.execute(_apply(count_stmt)).scalar() or 0)
            rows = session.execute(
                base.order_by(OrderExecutionModel.executed_at.desc())
                .offset(off)
                .limit(lim)
            ).all()
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
            return items, total
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
        offset: int = 0,
        open_only_latest: bool = False,
    ) -> tuple[list[PositionHistoryItemDTO], int]:
        session = get_db_session()
        try:
            lim = clamp_limit(limit)
            off = clamp_offset(offset)
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
                total = len(ids)
                page_ids = ids[off : off + lim]
                if not page_ids:
                    return [], total
                rows = session.execute(
                    select(PositionSnapshotModel).where(
                        PositionSnapshotModel.id.in_(page_ids)
                    )
                ).scalars().all()
                by_id = {r.id: r for r in rows}
                return (
                    [_position_history_item(by_id[i]) for i in page_ids if i in by_id],
                    total,
                )

            stmt = select(PositionSnapshotModel).where(
                PositionSnapshotModel.user_id == user_id
            )
            count_stmt = select(func.count()).select_from(PositionSnapshotModel).where(
                PositionSnapshotModel.user_id == user_id
            )

            def _apply(s):
                if run_id:
                    s = s.where(PositionSnapshotModel.run_id == run_id)
                if symbol:
                    s = s.where(PositionSnapshotModel.symbol == symbol)
                if status:
                    s = s.where(PositionSnapshotModel.status == status.upper())
                if from_at:
                    s = s.where(PositionSnapshotModel.snapshot_at >= from_at)
                if to_at:
                    s = s.where(PositionSnapshotModel.snapshot_at < to_at)
                return s

            stmt = _apply(stmt)
            total = int(session.execute(_apply(count_stmt)).scalar() or 0)
            rows = session.execute(
                stmt.order_by(PositionSnapshotModel.snapshot_at.desc())
                .offset(off)
                .limit(lim)
            ).scalars().all()
            return [_position_history_item(r) for r in rows], total
        finally:
            session.close()

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
        session = get_db_session()
        try:
            lim = clamp_limit(limit)
            off = clamp_offset(offset)
            stmt = select(TradeResultModel).where(TradeResultModel.user_id == user_id)
            count_stmt = select(func.count()).select_from(TradeResultModel).where(
                TradeResultModel.user_id == user_id
            )

            def _apply(s):
                if run_id:
                    s = s.where(TradeResultModel.run_id == run_id)
                if symbol:
                    s = s.where(TradeResultModel.symbol == symbol)
                if exit_reason:
                    s = s.where(TradeResultModel.exit_reason == exit_reason.upper())
                if is_win is not None:
                    s = s.where(TradeResultModel.is_win.is_(is_win))
                if from_at:
                    s = s.where(TradeResultModel.closed_at >= from_at)
                if to_at:
                    s = s.where(TradeResultModel.closed_at < to_at)
                return s

            stmt = _apply(stmt)
            total = int(session.execute(_apply(count_stmt)).scalar() or 0)
            rows = session.execute(
                stmt.order_by(TradeResultModel.closed_at.desc()).offset(off).limit(lim)
            ).scalars().all()
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
                        strategy_id=dto.strategy_id,
                        correlation_id=dto.correlation_id or "",
                        entry_notional_usdt=dto.entry_notional_usdt,
                        position_snapshot_id=dto.position_snapshot_id,
                        hold_seconds=dto.hold_seconds,
                    )
                )
            return items, total
        finally:
            session.close()

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
        session = get_db_session()
        try:
            lim = clamp_limit(limit)
            off = clamp_offset(offset)
            stmt = select(EquitySnapshotModel).where(
                EquitySnapshotModel.user_id == user_id
            )
            count_stmt = select(func.count()).select_from(EquitySnapshotModel).where(
                EquitySnapshotModel.user_id == user_id
            )

            def _apply(s):
                if run_id:
                    s = s.where(EquitySnapshotModel.run_id == run_id)
                if from_at:
                    s = s.where(EquitySnapshotModel.snapshot_at >= from_at)
                if to_at:
                    s = s.where(EquitySnapshotModel.snapshot_at < to_at)
                return s

            stmt = _apply(stmt)
            total = int(session.execute(_apply(count_stmt)).scalar() or 0)
            rows = session.execute(
                stmt.order_by(EquitySnapshotModel.snapshot_at.asc())
                .offset(off)
                .limit(lim)
            ).scalars().all()
            items = [
                EquityHistoryItemDTO(
                    id=r.id,
                    run_id=r.run_id,
                    snapshot_at=r.snapshot_at,
                    snapshot_date=r.snapshot_date.isoformat() if r.snapshot_date else "",
                    equity_usdt=r.equity_usdt,
                    cumulative_realized_pnl=r.cumulative_realized_pnl,
                    source=r.source,
                    paper_mode=r.paper_mode,
                )
                for r in rows
            ]
            return items, total
        finally:
            session.close()

    def get_tick_detail(
        self,
        *,
        correlation_id: str,
        user_id: str = "default",
    ) -> TickDetailDTO:
        """correlation_id로 시그널·주문·체결·포지션·청산·감사를 묶는다."""
        session = get_db_session()
        try:
            corr = correlation_id.strip()
            signals = session.execute(
                select(SignalEventModel)
                .where(
                    SignalEventModel.user_id == user_id,
                    SignalEventModel.correlation_id == corr,
                )
                .order_by(SignalEventModel.event_at.asc())
            ).scalars().all()
            orders = session.execute(
                select(OrderRequestModel)
                .where(
                    OrderRequestModel.user_id == user_id,
                    OrderRequestModel.correlation_id == corr,
                )
                .order_by(OrderRequestModel.requested_at.asc())
            ).scalars().all()
            order_ids = [o.id for o in orders]
            executions = []
            if order_ids:
                executions = session.execute(
                    select(OrderExecutionModel)
                    .where(OrderExecutionModel.order_request_id.in_(order_ids))
                    .order_by(OrderExecutionModel.executed_at.asc())
                ).scalars().all()
            trades = session.execute(
                select(TradeResultModel)
                .where(
                    TradeResultModel.user_id == user_id,
                    TradeResultModel.correlation_id == corr,
                )
                .order_by(TradeResultModel.closed_at.asc())
            ).scalars().all()
            audits = session.execute(
                select(AuditLogModel)
                .where(
                    AuditLogModel.user_id == user_id,
                    AuditLogModel.correlation_id == corr,
                )
                .order_by(AuditLogModel.created_at.asc())
            ).scalars().all()

            # position: correlation 컬럼 없음 → 동일 run/symbol OPEN/CLOSED 최근 스냅샷
            run_id = None
            symbol = None
            if orders:
                run_id = orders[0].run_id
                symbol = orders[0].symbol
            elif trades:
                run_id = trades[0].run_id
                symbol = trades[0].symbol
            elif signals:
                run_id = signals[0].run_id
                symbol = signals[0].symbol

            positions = []
            if run_id and symbol:
                positions = session.execute(
                    select(PositionSnapshotModel)
                    .where(
                        PositionSnapshotModel.user_id == user_id,
                        PositionSnapshotModel.run_id == run_id,
                        PositionSnapshotModel.symbol == symbol,
                    )
                    .order_by(PositionSnapshotModel.snapshot_at.desc())
                    .limit(10)
                ).scalars().all()

            # inference: correlation_id 컬럼 없음 → 동일 run/symbol 최근 N건
            inferences = []
            if run_id and symbol:
                inferences = session.execute(
                    select(ModelInferenceEventModel)
                    .where(
                        ModelInferenceEventModel.user_id == user_id,
                        ModelInferenceEventModel.run_id == run_id,
                        ModelInferenceEventModel.symbol == symbol,
                    )
                    .order_by(ModelInferenceEventModel.inference_at.desc())
                    .limit(5)
                ).scalars().all()

            return TickDetailDTO(
                correlation_id=corr,
                run_id=run_id,
                symbol=symbol,
                signals=serialize([to_signal_event_dto(s) for s in signals]),
                inferences=serialize([to_model_inference_dto(i) for i in inferences]),
                orders=serialize([to_order_request_dto(o) for o in orders]),
                executions=serialize([to_order_execution_dto(e) for e in executions]),
                positions=serialize([to_position_snapshot_dto(p) for p in positions]),
                trades=serialize([to_trade_result_dto(t) for t in trades]),
                audit_logs=serialize([to_audit_log_dto(a) for a in audits]),
            )
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

            open_positions, _ = self.list_positions(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                open_only_latest=True,
                limit=500,
                offset=0,
            )

            orders_total = _count_model(
                session,
                OrderRequestModel,
                OrderRequestModel.requested_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )
            executions_total = _count_model(
                session,
                OrderExecutionModel,
                OrderExecutionModel.executed_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
            )
            closed_positions = _count_model(
                session,
                PositionSnapshotModel,
                PositionSnapshotModel.snapshot_at,
                user_id,
                run_id,
                symbol,
                from_at,
                to_at,
                extra_status="CLOSED",
            )

            closed_trades_stmt = select(func.count()).where(
                TradeResultModel.user_id == user_id
            )
            pnl_stmt = select(
                func.coalesce(func.sum(TradeResultModel.realized_pnl), 0.0)
            ).where(TradeResultModel.user_id == user_id)
            win_stmt = select(func.count()).where(
                TradeResultModel.user_id == user_id,
                TradeResultModel.is_win.is_(True),
            )
            loss_stmt = select(func.count()).where(
                TradeResultModel.user_id == user_id,
                TradeResultModel.is_win.is_(False),
            )
            for s_name, filt in (
                ("run_id", run_id),
                ("symbol", symbol),
            ):
                if filt:
                    col = getattr(TradeResultModel, s_name)
                    closed_trades_stmt = closed_trades_stmt.where(col == filt)
                    pnl_stmt = pnl_stmt.where(col == filt)
                    win_stmt = win_stmt.where(col == filt)
                    loss_stmt = loss_stmt.where(col == filt)
            if from_at:
                closed_trades_stmt = closed_trades_stmt.where(
                    TradeResultModel.closed_at >= from_at
                )
                pnl_stmt = pnl_stmt.where(TradeResultModel.closed_at >= from_at)
                win_stmt = win_stmt.where(TradeResultModel.closed_at >= from_at)
                loss_stmt = loss_stmt.where(TradeResultModel.closed_at >= from_at)
            if to_at:
                closed_trades_stmt = closed_trades_stmt.where(
                    TradeResultModel.closed_at < to_at
                )
                pnl_stmt = pnl_stmt.where(TradeResultModel.closed_at < to_at)
                win_stmt = win_stmt.where(TradeResultModel.closed_at < to_at)
                loss_stmt = loss_stmt.where(TradeResultModel.closed_at < to_at)

            closed_trades = int(session.execute(closed_trades_stmt).scalar() or 0)
            realized_sum = float(session.execute(pnl_stmt).scalar() or 0.0)
            wins = int(session.execute(win_stmt).scalar() or 0)
            losses = int(session.execute(loss_stmt).scalar() or 0)
            decided = wins + losses
            win_rate = (wins / decided) if decided > 0 else None

            # filled / pending from latest execution join (accurate counts)
            LatestExec = aliased(OrderExecutionModel)
            latest_exec_sq = (
                select(
                    OrderExecutionModel.order_request_id.label("order_request_id"),
                    func.max(OrderExecutionModel.id).label("max_id"),
                )
                .where(OrderExecutionModel.user_id == user_id)
                .group_by(OrderExecutionModel.order_request_id)
                .subquery()
            )
            filled_stmt = (
                select(func.count())
                .select_from(OrderRequestModel)
                .join(
                    latest_exec_sq,
                    latest_exec_sq.c.order_request_id == OrderRequestModel.id,
                )
                .join(LatestExec, LatestExec.id == latest_exec_sq.c.max_id)
                .where(
                    OrderRequestModel.user_id == user_id,
                    LatestExec.status.in_(("FILLED", "PARTIAL")),
                )
            )
            pending_stmt = (
                select(func.count())
                .select_from(OrderRequestModel)
                .outerjoin(
                    latest_exec_sq,
                    latest_exec_sq.c.order_request_id == OrderRequestModel.id,
                )
                .where(
                    OrderRequestModel.user_id == user_id,
                    OrderRequestModel.order_id.is_not(None),
                    latest_exec_sq.c.max_id.is_(None),
                )
            )
            for s_name, filt in (("run_id", run_id), ("symbol", symbol)):
                if filt:
                    col = getattr(OrderRequestModel, s_name)
                    filled_stmt = filled_stmt.where(col == filt)
                    pending_stmt = pending_stmt.where(col == filt)
            if from_at:
                filled_stmt = filled_stmt.where(
                    OrderRequestModel.requested_at >= from_at
                )
                pending_stmt = pending_stmt.where(
                    OrderRequestModel.requested_at >= from_at
                )
            if to_at:
                filled_stmt = filled_stmt.where(OrderRequestModel.requested_at < to_at)
                pending_stmt = pending_stmt.where(
                    OrderRequestModel.requested_at < to_at
                )

            orders_filled = int(session.execute(filled_stmt).scalar() or 0)
            orders_pending = int(session.execute(pending_stmt).scalar() or 0)

            return EngineHistorySummaryDTO(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                engine_status=engine_status,
                open_positions=len(open_positions),
                orders_total=orders_total,
                orders_filled=orders_filled,
                orders_pending=orders_pending,
                orders_missing_db_execution=0,
                executions_total=executions_total,
                closed_positions=closed_positions,
                closed_trades=closed_trades,
                realized_pnl_sum=realized_sum,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                latest_signal_at=_latest_at(
                    session,
                    SignalEventModel,
                    SignalEventModel.event_at,
                    user_id,
                    run_id,
                    symbol,
                    from_at,
                    to_at,
                ),
                latest_order_at=_latest_at(
                    session,
                    OrderRequestModel,
                    OrderRequestModel.requested_at,
                    user_id,
                    run_id,
                    symbol,
                    from_at,
                    to_at,
                ),
                latest_execution_at=_latest_at(
                    session,
                    OrderExecutionModel,
                    OrderExecutionModel.executed_at,
                    user_id,
                    run_id,
                    symbol,
                    from_at,
                    to_at,
                ),
                latest_position_at=_latest_at(
                    session,
                    PositionSnapshotModel,
                    PositionSnapshotModel.snapshot_at,
                    user_id,
                    run_id,
                    symbol,
                    from_at,
                    to_at,
                ),
                filters={
                    "from_at": from_at.isoformat() if from_at else None,
                    "to_at": to_at.isoformat() if to_at else None,
                },
            )
        finally:
            session.close()


def _count_model(
    session,
    model,
    ts_col,
    user_id: str,
    run_id: str | None,
    symbol: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    extra_status: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(model).where(model.user_id == user_id)
    if run_id and hasattr(model, "run_id"):
        stmt = stmt.where(model.run_id == run_id)
    if symbol and hasattr(model, "symbol"):
        stmt = stmt.where(model.symbol == symbol)
    if from_at:
        stmt = stmt.where(ts_col >= from_at)
    if to_at:
        stmt = stmt.where(ts_col < to_at)
    if extra_status and hasattr(model, "status"):
        stmt = stmt.where(model.status == extra_status)
    return int(session.execute(stmt).scalar() or 0)


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
