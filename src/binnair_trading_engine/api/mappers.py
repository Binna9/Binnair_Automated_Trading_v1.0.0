"""
ORM 모델 → persistence DTO 변환.

DB row(SQLAlchemy Model)를 EngineRunDTO, SignalEventDTO 등으로 바꾼다.

왜 필요: repository는 ORM을 그대로 반환하지 않고,
API·엔진이 공유하는 DTO 형태로 통일해서 넘긴다.
"""
from __future__ import annotations

from binnair_trading_engine.infra.persistence.dto import (
    AuditLogDTO,
    EngineRunDTO,
    ModelInferenceEventDTO,
    OrderExecutionDTO,
    OrderRequestDTO,
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


def to_engine_run_dto(m: EngineRunModel) -> EngineRunDTO:
    return EngineRunDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        model_version=m.model_version,
        feature_set_version=m.feature_set_version,
        version=m.version,
        paper_mode=m.paper_mode,
        status=m.status,
        started_at=m.started_at,
        stopped_at=m.stopped_at,
        config_snapshot=m.config_snapshot,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def to_signal_event_dto(m: SignalEventModel) -> SignalEventDTO:
    return SignalEventDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        symbol=m.symbol,
        signal_action=m.signal_action,
        confidence=m.confidence,
        price_hint=m.price_hint,
        correlation_id=m.correlation_id or "",
        paper_mode=m.paper_mode,
        event_at=m.event_at,
        timeframe=m.timeframe,
        model_version=m.model_version,
        created_at=m.created_at,
    )


def to_order_request_dto(m: OrderRequestModel) -> OrderRequestDTO:
    return OrderRequestDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        symbol=m.symbol,
        side=m.side,
        order_type=m.order_type,
        quantity=m.quantity,
        price=m.price,
        stop_price=m.stop_price,
        reduce_only=m.reduce_only,
        position_side=m.position_side,
        correlation_id=m.correlation_id or "",
        paper_mode=m.paper_mode,
        requested_at=m.requested_at,
        order_id=m.order_id,
        client_order_id=m.client_order_id,
        created_at=m.created_at,
    )


def to_order_execution_dto(m: OrderExecutionModel) -> OrderExecutionDTO:
    return OrderExecutionDTO(
        id=m.id,
        user_id=m.user_id,
        order_request_id=m.order_request_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        symbol=m.symbol,
        order_id=m.order_id,
        status=m.status,
        executed_price=m.executed_price,
        executed_qty=m.executed_quantity,
        stop_price=m.stop_price,
        reduce_only=m.reduce_only,
        position_side=m.position_side,
        raw_response=m.raw_response,
        paper_mode=m.paper_mode,
        executed_at=m.executed_at,
        created_at=m.created_at,
    )


def to_position_snapshot_dto(m: PositionSnapshotModel) -> PositionSnapshotDTO:
    return PositionSnapshotDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        symbol=m.symbol,
        side=m.side,
        quantity=m.quantity,
        avg_entry_price=m.avg_entry_price,
        tp_price=m.tp_price,
        sl_price=m.sl_price,
        status=m.status,
        unrealized_pnl=m.unrealized_pnl,
        realized_pnl=m.realized_pnl,
        exit_reason=m.exit_reason,
        exit_price=m.exit_price,
        opened_at=m.opened_at,
        closed_at=m.closed_at,
        paper_mode=m.paper_mode,
        snapshot_at=m.snapshot_at,
        created_at=m.created_at,
    )


def to_model_inference_dto(m: ModelInferenceEventModel) -> ModelInferenceEventDTO:
    return ModelInferenceEventDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        strategy_id=m.strategy_id,
        symbol=m.symbol,
        model_version=m.model_version,
        feature_set_version=m.feature_set_version,
        input_snapshot=m.input_snapshot,
        output_prediction=m.output_prediction,
        paper_mode=m.paper_mode,
        inference_at=m.inference_at,
        created_at=m.created_at,
    )


def to_audit_log_dto(m: AuditLogModel) -> AuditLogDTO:
    return AuditLogDTO(
        id=m.id,
        user_id=m.user_id,
        run_id=m.run_id,
        correlation_id=m.correlation_id or "",
        event=m.event,
        data=m.data or {},
        paper_mode=m.paper_mode,
        created_at=m.created_at,
    )
