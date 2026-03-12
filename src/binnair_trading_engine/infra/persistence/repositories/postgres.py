"""
Postgres Repository 구현 스켈레톤.
TODO: 실제 DB 연결 후 구현 완성.
"""

from __future__ import annotations

import logging
from typing import Protocol

from binnair_trading_engine.infra.persistence.dto import (
    AuditLogCreate,
    EngineRunCreate,
    EngineRunStatus,
    ModelInferenceEventCreate,
    OrderExecutionCreate,
    OrderRequestCreate,
    PositionSnapshotCreate,
    RiskEventCreate,
    SignalEventCreate,
    StrategyConfigSnapshotCreate,
)
from binnair_trading_engine.infra.persistence.models import (
    AuditLogModel,
    EngineRunModel,
    ModelInferenceEventModel,
    OrderExecutionModel,
    OrderRequestModel,
    PositionSnapshotModel,
    RiskEventModel,
    SignalEventModel,
    StrategyConfigSnapshotModel,
)
from binnair_trading_engine.infra.persistence.session import get_engine

logger = logging.getLogger(__name__)


class _BasePostgresRepository:
    """공통 세션/엔진 접근."""

    def __init__(self) -> None:
        self._engine = get_engine()


class EngineRunPostgresRepository(_BasePostgresRepository):
    """engine_run 테이블 repository."""

    def create(self, dto: EngineRunCreate) -> str | None:
        # TODO: Session으로 insert, run_id 반환
        _ = dto
        return None

    def update_status(self, run_id: str, status: EngineRunStatus) -> None:
        # TODO: UPDATE engine_run SET status=?, stopped_at=? WHERE run_id=?
        _, _ = run_id, status
        pass

    def get_by_run_id(self, run_id: str) -> dict | None:
        # TODO: SELECT ... WHERE run_id=?
        _ = run_id
        return None


class StrategyConfigSnapshotPostgresRepository(_BasePostgresRepository):
    """strategy_config_snapshot 테이블 repository."""

    def create(self, dto: StrategyConfigSnapshotCreate) -> int | None:
        _ = dto
        return None


class SignalEventPostgresRepository(_BasePostgresRepository):
    """signal_event 테이블 repository."""

    def create(self, dto: SignalEventCreate) -> int | None:
        _ = dto
        return None


class OrderRequestPostgresRepository(_BasePostgresRepository):
    """order_request 테이블 repository."""

    def create(self, dto: OrderRequestCreate) -> int | None:
        _ = dto
        return None


class OrderExecutionPostgresRepository(_BasePostgresRepository):
    """order_execution 테이블 repository."""

    def create(self, dto: OrderExecutionCreate) -> int | None:
        _ = dto
        return None


class PositionSnapshotPostgresRepository(_BasePostgresRepository):
    """position_snapshot 테이블 repository."""

    def create(self, dto: PositionSnapshotCreate) -> int | None:
        _ = dto
        return None


class RiskEventPostgresRepository(_BasePostgresRepository):
    """risk_event 테이블 repository."""

    def create(self, dto: RiskEventCreate) -> int | None:
        _ = dto
        return None


class ModelInferenceEventPostgresRepository(_BasePostgresRepository):
    """model_inference_event 테이블 repository."""

    def create(self, dto: ModelInferenceEventCreate) -> int | None:
        _ = dto
        return None


class AuditLogPostgresRepository(_BasePostgresRepository):
    """audit_log 테이블 repository."""

    def create(self, dto: AuditLogCreate) -> int | None:
        _ = dto
        return None


class PostgresRepositoryFactory:
    """Postgres repository 팩토리."""

    def __init__(self) -> None:
        self._engine_run = EngineRunPostgresRepository()
        self._strategy_config = StrategyConfigSnapshotPostgresRepository()
        self._signal_event = SignalEventPostgresRepository()
        self._order_request = OrderRequestPostgresRepository()
        self._order_execution = OrderExecutionPostgresRepository()
        self._position_snapshot = PositionSnapshotPostgresRepository()
        self._risk_event = RiskEventPostgresRepository()
        self._model_inference = ModelInferenceEventPostgresRepository()
        self._audit_log = AuditLogPostgresRepository()

    @property
    def engine_run(self) -> EngineRunPostgresRepository:
        return self._engine_run

    @property
    def strategy_config_snapshot(self) -> StrategyConfigSnapshotPostgresRepository:
        return self._strategy_config

    @property
    def signal_event(self) -> SignalEventPostgresRepository:
        return self._signal_event

    @property
    def order_request(self) -> OrderRequestPostgresRepository:
        return self._order_request

    @property
    def order_execution(self) -> OrderExecutionPostgresRepository:
        return self._order_execution

    @property
    def position_snapshot(self) -> PositionSnapshotPostgresRepository:
        return self._position_snapshot

    @property
    def risk_event(self) -> RiskEventPostgresRepository:
        return self._risk_event

    @property
    def model_inference_event(self) -> ModelInferenceEventPostgresRepository:
        return self._model_inference

    @property
    def audit_log(self) -> AuditLogPostgresRepository:
        return self._audit_log
