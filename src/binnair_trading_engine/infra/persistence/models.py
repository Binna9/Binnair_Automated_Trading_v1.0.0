"""
SQLAlchemy 2.x DB 모델.
자동매매 엔진 실행 이력 추적용.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, MetaData, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "trade"
metadata = MetaData(schema=SCHEMA)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    metadata = metadata


# ---------------------------------------------------------------------------
# engine_run
# ---------------------------------------------------------------------------
class EngineRunModel(Base):
    """
    엔진 실행 이력. (BinnAIR pipeline_runs 유사)
    run_id 기준 실행 단위 추적.
    """

    __tablename__ = "engine_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    feature_set_version: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|stopped|error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# strategy_config_snapshot
# ---------------------------------------------------------------------------
class StrategyConfigSnapshotModel(Base):
    """
    전략 설정 스냅샷.
    실행 시점 전략 파라미터 보관 (replay/debug용).
    """

    __tablename__ = "strategy_config_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config_json: Mapped[dict] = mapped_column(JSONB)
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# signal_event
# ---------------------------------------------------------------------------
class SignalEventModel(Base):
    """
    시그널 이벤트.
    Predictor/Strategy 출력 BUY|SELL|HOLD 기록.
    """

    __tablename__ = "signal_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(16), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    signal_action: Mapped[str] = mapped_column(String(16))  # BUY|SELL|HOLD
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    price_hint: Mapped[float | None] = mapped_column(Float, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("ix_signal_event_run_symbol_at", "run_id", "symbol", "event_at"),)


# ---------------------------------------------------------------------------
# order_request
# ---------------------------------------------------------------------------
class OrderRequestModel(Base):
    """
    주문 요청 (엔진 → 거래소 전달 직전).
    """

    __tablename__ = "order_request"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # 거래소 order_id
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    side: Mapped[str] = mapped_column(String(16))  # BUY|SELL
    order_type: Mapped[str] = mapped_column(String(16))  # MARKET|LIMIT
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# order_execution
# ---------------------------------------------------------------------------
class OrderExecutionModel(Base):
    """
    주문 체결/실행 결과.
    raw_response: 거래소 응답 원문 저장.
    """

    __tablename__ = "order_execution"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_request.id"), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))  # FILLED|CANCELLED|REJECTED
    executed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    executed_quantity: Mapped[float] = mapped_column(Float)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 거래소 원문
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# position_snapshot
# ---------------------------------------------------------------------------
class PositionSnapshotModel(Base):
    """
    포지션 스냅샷.
    특정 시점 포지션 상태 (replay/debug).
    """

    __tablename__ = "position_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    avg_entry_price: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("ix_position_snapshot_run_symbol_at", "run_id", "symbol", "snapshot_at"),)


# ---------------------------------------------------------------------------
# risk_event
# ---------------------------------------------------------------------------
class RiskEventModel(Base):
    """
    리스크 이벤트 (거부, 경고 등).
    """

    __tablename__ = "risk_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64))  # risk_rejected, etc.
    reason: Mapped[str] = mapped_column(Text)
    intent_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# model_inference_event
# ---------------------------------------------------------------------------
class ModelInferenceEventModel(Base):
    """
    모델 추론 이벤트.
    input_snapshot, output_prediction 저장 (replay/debug).
    """

    __tablename__ = "model_inference_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    feature_set_version: Mapped[str] = mapped_column(String(64), index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)  # MarketSnapshot
    output_prediction: Mapped[dict] = mapped_column(JSONB)  # Prediction
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    inference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------
class AuditLogModel(Base):
    """
    감사 로그.
    모든 주요 이벤트의 최종 기록.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    event: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
