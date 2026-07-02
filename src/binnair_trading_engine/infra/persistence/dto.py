"""
Repository 입출력용 DTO를 정의한다.
도메인 객체와 DB ORM 모델 사이의 저장 요청 데이터를 명확히 분리한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class EngineRunDTO:
    """engine_run 테이블용 DTO."""

    run_id: str
    strategy_id: str
    model_version: str
    feature_set_version: str
    version: str
    paper_mode: bool
    status: str
    started_at: datetime
    stopped_at: datetime | None = None
    config_snapshot: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    user_id: str = "default"
    id: int | None = None


@dataclass
class StrategyConfigSnapshotDTO:
    """strategy_config_snapshot 테이블용 DTO."""

    run_id: str
    strategy_id: str
    snapshot_at: datetime
    config_json: dict[str, Any]
    paper_mode: bool
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class SignalEventDTO:
    """signal_event 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    signal_action: str
    confidence: float
    price_hint: float | None
    correlation_id: str
    paper_mode: bool
    event_at: datetime
    timeframe: str | None = None
    model_version: str | None = None
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class OrderRequestDTO:
    """order_request 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    stop_price: float | None
    reduce_only: bool
    position_side: str
    correlation_id: str
    paper_mode: bool
    requested_at: datetime
    order_id: str | None = None
    client_order_id: str | None = None
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class OrderExecutionDTO:
    """order_execution 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    order_id: str
    status: str
    executed_price: float | None
    executed_qty: float
    stop_price: float | None
    reduce_only: bool
    position_side: str
    raw_response: dict[str, Any] | None
    paper_mode: bool
    executed_at: datetime
    order_request_id: int | None = None
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class PositionSnapshotDTO:
    """position_snapshot 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float
    paper_mode: bool
    snapshot_at: datetime
    side: str | None = None
    tp_price: float | None = None
    sl_price: float | None = None
    status: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    realized_pnl: float | None = None
    exit_reason: str | None = None
    exit_price: float | None = None
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class RiskEventDTO:
    """risk_event 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    event_type: str
    reason: str
    intent_data: dict[str, Any] | None
    paper_mode: bool
    event_at: datetime
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class ModelInferenceEventDTO:
    """model_inference_event 테이블용 DTO."""

    run_id: str
    strategy_id: str
    symbol: str
    model_version: str
    feature_set_version: str
    input_snapshot: dict[str, Any]
    output_prediction: dict[str, Any]
    paper_mode: bool
    inference_at: datetime
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


@dataclass
class AuditLogDTO:
    """audit_log 테이블용 DTO."""

    run_id: str
    event: str
    data: dict[str, Any]
    paper_mode: bool
    correlation_id: str = ""
    user_id: str = "default"
    created_at: datetime | None = None
    id: int | None = None


# ---------------------------------------------------------------------------
# Create DTOs (repository 입력용)
# ---------------------------------------------------------------------------

EngineRunStatus = str  # "running" | "stopped" | "error"


@dataclass
class EngineRunCreate:
    run_id: str
    strategy_id: str
    model_version: str
    feature_set_version: str
    version: str
    paper_mode: bool
    started_at: datetime
    config_snapshot: dict[str, Any] | None = None
    user_id: str = "default"


@dataclass
class StrategyConfigSnapshotCreate:
    run_id: str
    strategy_id: str
    snapshot_at: datetime
    config_json: dict[str, Any]
    paper_mode: bool
    user_id: str = "default"


@dataclass
class SignalEventCreate:
    run_id: str
    strategy_id: str
    symbol: str
    signal_action: str
    confidence: float
    price_hint: float | None
    correlation_id: str
    paper_mode: bool
    event_at: datetime
    timeframe: str | None = None
    model_version: str | None = None
    user_id: str = "default"


@dataclass
class OrderRequestCreate:
    run_id: str
    strategy_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    stop_price: float | None
    reduce_only: bool
    position_side: str
    correlation_id: str
    paper_mode: bool
    requested_at: datetime
    order_id: str | None = None
    client_order_id: str | None = None
    user_id: str = "default"


@dataclass
class OrderExecutionCreate:
    run_id: str
    strategy_id: str
    symbol: str
    order_id: str
    status: str
    executed_price: float | None
    executed_qty: float
    stop_price: float | None
    reduce_only: bool
    position_side: str
    raw_response: dict[str, Any] | None
    paper_mode: bool
    executed_at: datetime
    order_request_id: int | None = None
    user_id: str = "default"


@dataclass
class PositionSnapshotCreate:
    run_id: str
    strategy_id: str
    symbol: str
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float
    paper_mode: bool
    snapshot_at: datetime
    side: str | None = None  # LONG | SHORT
    tp_price: float | None = None
    sl_price: float | None = None
    status: str | None = None  # OPEN | CLOSED
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    realized_pnl: float | None = None  # 청산 시 실현 손익
    exit_reason: str | None = None  # TAKE_PROFIT | STOP_LOSS
    exit_price: float | None = None  # 청산가
    user_id: str = "default"


@dataclass
class RiskEventCreate:
    run_id: str
    strategy_id: str
    symbol: str
    event_type: str
    reason: str
    intent_data: dict[str, Any] | None
    paper_mode: bool
    event_at: datetime
    user_id: str = "default"


@dataclass
class ModelInferenceEventCreate:
    run_id: str
    strategy_id: str
    symbol: str
    model_version: str
    feature_set_version: str
    input_snapshot: dict[str, Any]
    output_prediction: dict[str, Any]
    paper_mode: bool
    inference_at: datetime
    user_id: str = "default"


@dataclass
class AuditLogCreate:
    run_id: str
    event: str
    data: dict[str, Any]
    paper_mode: bool
    correlation_id: str = ""
    user_id: str = "default"


@dataclass
class OhlcvCandleCreate:
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trade_count: int | None = None
