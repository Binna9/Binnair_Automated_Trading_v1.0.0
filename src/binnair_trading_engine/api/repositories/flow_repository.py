"""
매매 이력 DB 조회 (read-only).

포지션, 시그널, 주문, 타임라인, 대시보드 등을 Postgres에서 읽는다.
엔진의 write repository(postgres.py)와 역할이 다르다 — 여기는 SELECT만.

왜 필요: "어떤 데이터를 어떻게 가져올지" SQL·조합 로직을
HTTP 라우트(flow_controller.py)와 분리해 한곳에 모은다.
"""
from __future__ import annotations

from datetime import datetime

from binnair_trading_engine.infra.timezone import kst_today_start, now_kst

from sqlalchemy import select, text

from binnair_trading_engine.api.common.db import get_db_session
from binnair_trading_engine.api.dto.flow import (
    DashboardSummaryDTO,
    FlowTimelineItemDTO,
    OrderFlowDTO,
)
from binnair_trading_engine.api.common.mappers import (
    to_audit_log_dto,
    to_engine_run_dto,
    to_model_inference_dto,
    to_order_execution_dto,
    to_order_request_dto,
    to_position_snapshot_dto,
    to_signal_event_dto,
)
from binnair_trading_engine.api.common.serialize import dto_to_dict
from binnair_trading_engine.infra.persistence.dto import (
    AuditLogDTO,
    EngineRunDTO,
    ModelInferenceEventDTO,
    PositionSnapshotDTO,
    SignalEventDTO,
)
from binnair_trading_engine.infra.persistence.models import (
    AuditLogModel,
    EngineRunModel,
    ModelInferenceEventModel,
    OrderExecutionModel,
    OrderRequestModel,
    PositionSnapshotModel,
    SignalEventModel,
)


class FlowQueryRepository:
    """매매 이력·흐름 조회."""

    def list_engine_runs(
        self,
        *,
        user_id: str = "default",
        limit: int = 20,
        status: str | None = None,
    ) -> list[EngineRunDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(EngineRunModel)
                .where(EngineRunModel.user_id == user_id)
                .order_by(EngineRunModel.started_at.desc())
                .limit(max(1, min(limit, 200)))
            )
            if status:
                stmt = stmt.where(EngineRunModel.status == status)
            rows = session.execute(stmt).scalars().all()
            return [to_engine_run_dto(r) for r in rows]
        finally:
            session.close()

    def get_engine_run(
        self, run_id: str, *, user_id: str = "default"
    ) -> EngineRunDTO | None:
        session = get_db_session()
        try:
            stmt = select(EngineRunModel).where(
                EngineRunModel.run_id == run_id,
                EngineRunModel.user_id == user_id,
            )
            row = session.execute(stmt).scalars().first()
            return to_engine_run_dto(row) if row else None
        finally:
            session.close()

    def list_open_positions(
        self,
        *,
        user_id: str = "default",
        symbol: str | None = None,
    ) -> list[PositionSnapshotDTO]:
        session = get_db_session()
        try:
            schema = PositionSnapshotModel.__table__.schema or "trade"
            sql = f"""
                SELECT id FROM (
                    SELECT DISTINCT ON (symbol) id, status, quantity
                    FROM "{schema}".position_snapshot
                    WHERE user_id = :user_id
            """
            params: dict = {"user_id": user_id}
            if symbol:
                sql += " AND symbol = :symbol"
                params["symbol"] = symbol
            sql += """
                    ORDER BY symbol, snapshot_at DESC
                ) latest
                WHERE latest.status = 'OPEN' AND latest.quantity > 0
            """
            id_rows = session.execute(text(sql), params).all()
            ids = [row[0] for row in id_rows]
            if not ids:
                return []
            stmt = select(PositionSnapshotModel).where(PositionSnapshotModel.id.in_(ids))
            rows = session.execute(stmt).scalars().all()
            by_id = {r.id: r for r in rows}
            return [to_position_snapshot_dto(by_id[i]) for i in ids if i in by_id]
        finally:
            session.close()

    def list_positions(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PositionSnapshotDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(PositionSnapshotModel)
                .where(PositionSnapshotModel.user_id == user_id)
                .order_by(PositionSnapshotModel.snapshot_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            if run_id:
                stmt = stmt.where(PositionSnapshotModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(PositionSnapshotModel.symbol == symbol)
            if status:
                stmt = stmt.where(PositionSnapshotModel.status == status)
            rows = session.execute(stmt).scalars().all()
            return [to_position_snapshot_dto(r) for r in rows]
        finally:
            session.close()

    def list_signals(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[SignalEventDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(SignalEventModel)
                .where(SignalEventModel.user_id == user_id)
                .order_by(SignalEventModel.event_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            if run_id:
                stmt = stmt.where(SignalEventModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(SignalEventModel.symbol == symbol)
            rows = session.execute(stmt).scalars().all()
            return [to_signal_event_dto(r) for r in rows]
        finally:
            session.close()

    def list_inferences(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[ModelInferenceEventDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(ModelInferenceEventModel)
                .where(ModelInferenceEventModel.user_id == user_id)
                .order_by(ModelInferenceEventModel.inference_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            if run_id:
                stmt = stmt.where(ModelInferenceEventModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(ModelInferenceEventModel.symbol == symbol)
            rows = session.execute(stmt).scalars().all()
            return [to_model_inference_dto(r) for r in rows]
        finally:
            session.close()

    def list_order_flows(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[OrderFlowDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(OrderRequestModel)
                .where(OrderRequestModel.user_id == user_id)
                .order_by(OrderRequestModel.requested_at.desc())
                .limit(max(1, min(limit, 200)))
            )
            if run_id:
                stmt = stmt.where(OrderRequestModel.run_id == run_id)
            if symbol:
                stmt = stmt.where(OrderRequestModel.symbol == symbol)
            requests = session.execute(stmt).scalars().all()
            flows: list[OrderFlowDTO] = []
            for req in requests:
                exec_stmt = (
                    select(OrderExecutionModel)
                    .where(OrderExecutionModel.order_request_id == req.id)
                    .order_by(OrderExecutionModel.executed_at.asc())
                )
                execs = session.execute(exec_stmt).scalars().all()
                flows.append(
                    OrderFlowDTO(
                        request=to_order_request_dto(req),
                        executions=[to_order_execution_dto(e) for e in execs],
                    )
                )
            return flows
        finally:
            session.close()

    def list_audit_logs(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogDTO]:
        session = get_db_session()
        try:
            stmt = (
                select(AuditLogModel)
                .where(AuditLogModel.user_id == user_id)
                .order_by(AuditLogModel.created_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            if run_id:
                stmt = stmt.where(AuditLogModel.run_id == run_id)
            rows = session.execute(stmt).scalars().all()
            return [to_audit_log_dto(r) for r in rows]
        finally:
            session.close()

    def get_realized_pnl_today(
        self, *, user_id: str = "default", run_id: str | None = None
    ) -> float:
        session = get_db_session()
        try:
            today = kst_today_start()
            schema = PositionSnapshotModel.__table__.schema or "trade"
            sql = f"""
                SELECT COALESCE(SUM(realized_pnl), 0)
                FROM "{schema}".position_snapshot
                WHERE user_id = :user_id
                  AND status = 'CLOSED'
                  AND closed_at >= :today
                  AND realized_pnl IS NOT NULL
            """
            params: dict = {"user_id": user_id, "today": today}
            if run_id:
                sql += " AND run_id = :run_id"
                params["run_id"] = run_id
            result = session.execute(text(sql), params).scalar()
            return float(result or 0.0)
        finally:
            session.close()

    def count_closed_positions_today(
        self, *, user_id: str = "default", run_id: str | None = None
    ) -> int:
        session = get_db_session()
        try:
            today = kst_today_start()
            stmt = select(PositionSnapshotModel).where(
                PositionSnapshotModel.user_id == user_id,
                PositionSnapshotModel.status == "CLOSED",
                PositionSnapshotModel.closed_at >= today,
            )
            if run_id:
                stmt = stmt.where(PositionSnapshotModel.run_id == run_id)
            rows = session.execute(stmt).scalars().all()
            return len(rows)
        finally:
            session.close()

    def get_flow_timeline(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[FlowTimelineItemDTO]:
        cap = max(1, min(limit, 500))
        per_table = max(cap // 5, 20)

        inferences = self.list_inferences(
            user_id=user_id, run_id=run_id, symbol=symbol, limit=per_table
        )
        signals = self.list_signals(
            user_id=user_id, run_id=run_id, symbol=symbol, limit=per_table
        )
        orders = self.list_order_flows(
            user_id=user_id, run_id=run_id, symbol=symbol, limit=per_table
        )
        positions = self.list_positions(
            user_id=user_id, run_id=run_id, symbol=symbol, limit=per_table
        )
        audits = self.list_audit_logs(user_id=user_id, run_id=run_id, limit=per_table)

        items: list[FlowTimelineItemDTO] = []

        for dto in inferences:
            pred = dto.output_prediction if isinstance(dto.output_prediction, dict) else {}
            action = pred.get("action", "?")
            conf = pred.get("confidence")
            conf_txt = f" conf={conf:.2f}" if isinstance(conf, (int, float)) else ""
            reason = pred.get("hold_reason")
            reason_txt = f" reason={reason}" if reason else ""
            items.append(
                FlowTimelineItemDTO(
                    event_type="inference",
                    event_at=dto.inference_at,
                    run_id=dto.run_id,
                    symbol=dto.symbol,
                    summary=f"TimesFM {action}{conf_txt}{reason_txt}",
                    correlation_id=None,
                    payload=dto_to_dict(dto),
                )
            )

        for dto in signals:
            items.append(
                FlowTimelineItemDTO(
                    event_type="signal",
                    event_at=dto.event_at,
                    run_id=dto.run_id,
                    symbol=dto.symbol,
                    summary=f"Signal {dto.signal_action} conf={dto.confidence:.2f}",
                    correlation_id=dto.correlation_id or None,
                    payload=dto_to_dict(dto),
                )
            )

        for flow in orders:
            req = flow.request
            items.append(
                FlowTimelineItemDTO(
                    event_type="order_request",
                    event_at=req.requested_at,
                    run_id=req.run_id,
                    symbol=req.symbol,
                    summary=f"Order {req.side} {req.quantity} {req.symbol} ({req.order_type})",
                    correlation_id=req.correlation_id or None,
                    payload=dto_to_dict(flow),
                )
            )
            for ex in flow.executions:
                items.append(
                    FlowTimelineItemDTO(
                        event_type="order_execution",
                        event_at=ex.executed_at,
                        run_id=ex.run_id,
                        symbol=ex.symbol,
                        summary=f"Fill {ex.status} {ex.executed_qty} @ {ex.executed_price}",
                        correlation_id=req.correlation_id or None,
                        payload=dto_to_dict(ex),
                    )
                )

        for dto in positions:
            pos_status = dto.status or "?"
            if pos_status == "OPEN":
                summary = (
                    f"Position OPEN {dto.side or 'LONG'} qty={dto.quantity} "
                    f"entry={dto.avg_entry_price} tp={dto.tp_price} sl={dto.sl_price}"
                )
            else:
                summary = (
                    f"Position CLOSED {dto.exit_reason or ''} "
                    f"pnl={dto.realized_pnl} exit={dto.exit_price}"
                )
            items.append(
                FlowTimelineItemDTO(
                    event_type="position",
                    event_at=dto.snapshot_at,
                    run_id=dto.run_id,
                    symbol=dto.symbol,
                    summary=summary.strip(),
                    correlation_id=None,
                    payload=dto_to_dict(dto),
                )
            )

        for dto in audits:
            items.append(
                FlowTimelineItemDTO(
                    event_type="audit",
                    event_at=dto.created_at or now_kst(),
                    run_id=dto.run_id,
                    symbol=(dto.data or {}).get("intent_symbol"),
                    summary=f"Audit {dto.event}"
                    + (f" ({dto.data.get('reason')})" if dto.data.get("reason") else ""),
                    correlation_id=dto.correlation_id or None,
                    payload=dto_to_dict(dto),
                )
            )

        items.sort(key=lambda x: x.event_at, reverse=True)
        return items[:cap]

    def get_dashboard(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
    ) -> DashboardSummaryDTO:
        runs = self.list_engine_runs(user_id=user_id, limit=1)
        latest = runs[0] if runs else None
        effective_run_id = run_id or (latest.run_id if latest else None)

        return DashboardSummaryDTO(
            user_id=user_id,
            latest_run=latest,
            open_positions=self.list_open_positions(user_id=user_id, symbol=symbol),
            closed_positions_today=self.count_closed_positions_today(
                user_id=user_id, run_id=effective_run_id
            ),
            realized_pnl_today=self.get_realized_pnl_today(
                user_id=user_id, run_id=effective_run_id
            ),
            recent_timeline=self.get_flow_timeline(
                user_id=user_id,
                run_id=effective_run_id,
                symbol=symbol,
                limit=15,
            ),
        )
