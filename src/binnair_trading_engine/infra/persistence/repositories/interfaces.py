"""
Repository 인터페이스.
Persistence 추상화. 구현체는 infra 레이어에서 주입.
"""
from __future__ import annotations

from typing import Protocol

from binnair_trading_engine.infra.persistence.dto import (
    AuditLogCreate,
    EngineRunCreate,
    EngineRunStatus,
    ModelInferenceEventCreate,
    OhlcvCandleCreate,
    OrderExecutionCreate,
    OrderRequestCreate,
    PositionSnapshotCreate,
    RiskEventCreate,
    SignalEventCreate,
    StrategyConfigSnapshotCreate,
)


class OhlcvCandleRepository(Protocol):
    """ohlcv_candle 저장소 인터페이스."""

    def upsert_many(self, candles: list[OhlcvCandleCreate]) -> int: ...
    def get_recent_closes(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[float]: ...


class EngineRunRepository(Protocol):
    """engine_run 저장소 인터페이스."""

    def create(self, dto: EngineRunCreate) -> str | None: ...
    def update_status(self, run_id: str, status: EngineRunStatus) -> None: ...
    def get_by_run_id(self, run_id: str) -> dict | None: ...


class StrategyConfigSnapshotRepository(Protocol):
    """strategy_config_snapshot 저장소 인터페이스."""

    def create(self, dto: StrategyConfigSnapshotCreate) -> int | None: ...


class SignalEventRepository(Protocol):
    """signal_event 저장소 인터페이스."""

    def create(self, dto: SignalEventCreate) -> int | None: ...


class OrderRequestRepository(Protocol):
    """order_request 저장소 인터페이스."""

    def create(self, dto: OrderRequestCreate) -> int | None: ...


class OrderExecutionRepository(Protocol):
    """order_execution 저장소 인터페이스."""

    def create(self, dto: OrderExecutionCreate) -> int | None: ...


class PositionSnapshotRepository(Protocol):
    """position_snapshot 저장소 인터페이스."""

    def create(self, dto: PositionSnapshotCreate) -> int | None: ...


class RiskEventRepository(Protocol):
    """risk_event 저장소 인터페이스."""

    def create(self, dto: RiskEventCreate) -> int | None: ...


class ModelInferenceEventRepository(Protocol):
    """model_inference_event 저장소 인터페이스."""

    def create(self, dto: ModelInferenceEventCreate) -> int | None: ...


class AuditLogRepository(Protocol):
    """audit_log 저장소 인터페이스."""

    def create(self, dto: AuditLogCreate) -> int | None: ...
