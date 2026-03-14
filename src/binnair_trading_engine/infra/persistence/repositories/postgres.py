"""
Postgres Repository 구현.
SQLAlchemy 2.x Session 기반 INSERT/SELECT.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.orm import Session

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
from binnair_trading_engine.infra.persistence.session import get_engine, get_session_factory

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import Order

logger = logging.getLogger(__name__)

_session_factory_cache = None


def _get_session_factory():
    global _session_factory_cache
    if _session_factory_cache is None:
        _session_factory_cache = get_session_factory(get_engine())
    return _session_factory_cache


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _session_scope():
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class _BasePostgresRepository:
    """공통 세션 팩토리."""

    def _session(self) -> Session:
        return _get_session_factory()()


class EngineRunPostgresRepository(_BasePostgresRepository):
    """engine_run 테이블 repository."""

    def create(self, dto: EngineRunCreate) -> str | None:
        session = self._session()
        try:
            existing = session.execute(
                select(EngineRunModel).where(EngineRunModel.run_id == dto.run_id)
            ).scalars().first()
            if existing:
                existing.status = "running"
                existing.started_at = dto.started_at
                existing.stopped_at = None
                existing.config_snapshot = dto.config_snapshot
                session.commit()
                return dto.run_id
            m = EngineRunModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                model_version=dto.model_version,
                feature_set_version=dto.feature_set_version,
                version="1.0.0",
                paper_mode=dto.paper_mode,
                status="running",
                started_at=dto.started_at,
                config_snapshot=dto.config_snapshot,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return dto.run_id
        except Exception as e:
            session.rollback()
            logger.exception("EngineRun create failed: %s", e)
            raise
        finally:
            session.close()

    def update_status(self, run_id: str, status: EngineRunStatus) -> None:
        session = self._session()
        try:
            stmt = (
                select(EngineRunModel)
                .where(EngineRunModel.run_id == run_id)
            )
            row = session.execute(stmt).scalars().first()
            if row:
                row.status = status
                row.stopped_at = datetime.now(timezone.utc)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("EngineRun update_status failed: %s", e)
            raise
        finally:
            session.close()

    def get_by_run_id(self, run_id: str) -> dict | None:
        session = self._session()
        try:
            stmt = select(EngineRunModel).where(EngineRunModel.run_id == run_id)
            row = session.execute(stmt).scalars().first()
            return row.__dict__ if row else None
        finally:
            session.close()


class StrategyConfigSnapshotPostgresRepository(_BasePostgresRepository):
    """strategy_config_snapshot 테이블 repository."""

    def create(self, dto: StrategyConfigSnapshotCreate) -> int | None:
        session = self._session()
        try:
            m = StrategyConfigSnapshotModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                snapshot_at=dto.snapshot_at,
                config_json=dto.config_json,
                paper_mode=dto.paper_mode,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("StrategyConfigSnapshot create failed: %s", e)
            raise
        finally:
            session.close()


class SignalEventPostgresRepository(_BasePostgresRepository):
    """signal_event 테이블 repository."""

    def create(self, dto: SignalEventCreate) -> int | None:
        session = self._session()
        try:
            m = SignalEventModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                signal_action=dto.signal_action,
                confidence=dto.confidence,
                price_hint=dto.price_hint,
                correlation_id=dto.correlation_id or "",
                paper_mode=dto.paper_mode,
                event_at=dto.event_at,
                timeframe=dto.timeframe,
                model_version=dto.model_version or "",
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("SignalEvent create failed: %s", e)
            raise
        finally:
            session.close()


class OrderRequestPostgresRepository(_BasePostgresRepository):
    """order_request 테이블 repository."""

    def create(self, dto: OrderRequestCreate) -> int | None:
        session = self._session()
        try:
            m = OrderRequestModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                side=dto.side,
                order_type=dto.order_type,
                quantity=dto.quantity,
                price=dto.price,
                correlation_id=dto.correlation_id or "",
                paper_mode=dto.paper_mode,
                requested_at=dto.requested_at,
                order_id=dto.order_id,
                client_order_id=dto.client_order_id,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("OrderRequest create failed: %s", e)
            raise
        finally:
            session.close()

    def get_recent(
        self, run_id: str, symbol: str, limit: int = 50
    ) -> list["Order"]:
        from binnair_trading_engine.domain.models import (
            Order,
            OrderSide,
            OrderStatus,
            OrderType,
        )

        session = self._session()
        try:
            stmt = (
                select(OrderRequestModel)
                .where(
                    OrderRequestModel.run_id == run_id,
                    OrderRequestModel.symbol == symbol,
                )
                .order_by(OrderRequestModel.requested_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                Order(
                    symbol=r.symbol,
                    side=OrderSide(r.side),
                    order_type=OrderType(r.order_type),
                    quantity=r.quantity,
                    price=r.price,
                    status=OrderStatus.PENDING,
                    order_id=r.order_id or "",
                    client_order_id=r.client_order_id,
                    run_id=r.run_id,
                    correlation_id=r.correlation_id or "",
                    created_at=_ensure_utc(r.requested_at),
                    updated_at=_ensure_utc(r.requested_at),
                )
                for r in rows
            ]
        finally:
            session.close()


class OrderExecutionPostgresRepository(_BasePostgresRepository):
    """order_execution 테이블 repository."""

    def create(self, dto: OrderExecutionCreate) -> int | None:
        session = self._session()
        try:
            m = OrderExecutionModel(
                order_request_id=dto.order_request_id,
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                order_id=dto.order_id,
                status=dto.status,
                executed_price=dto.executed_price,
                executed_quantity=dto.executed_qty,
                raw_response=dto.raw_response,
                paper_mode=dto.paper_mode,
                executed_at=dto.executed_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("OrderExecution create failed: %s", e)
            raise
        finally:
            session.close()

    def get_daily_pnl(self, run_id: str) -> float:
        """당일 실현손익 (SELL +, BUY -). order_request와 join해 side 사용."""
        session = self._session()
        try:
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            schema = OrderExecutionModel.__table__.schema or "trade"
            stmt = text(f"""
                SELECT req.side, ex.executed_price, ex.executed_quantity
                FROM "{schema}".order_execution ex
                JOIN "{schema}".order_request req ON ex.order_request_id = req.id
                WHERE ex.run_id = :run_id AND ex.executed_at >= :today
            """)
            result = session.execute(stmt, {"run_id": run_id, "today": today})
            pnl = 0.0
            for row in result:
                side, price, qty = row[0], row[1] or 0.0, row[2] or 0.0
                sign = 1.0 if side == "SELL" else -1.0
                pnl += sign * price * qty
            return pnl
        finally:
            session.close()


class PositionSnapshotPostgresRepository(_BasePostgresRepository):
    """position_snapshot 테이블 repository."""

    def create(self, dto: PositionSnapshotCreate) -> int | None:
        session = self._session()
        try:
            m = PositionSnapshotModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                quantity=dto.quantity,
                avg_entry_price=dto.avg_entry_price,
                unrealized_pnl=dto.unrealized_pnl,
                paper_mode=dto.paper_mode,
                snapshot_at=dto.snapshot_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("PositionSnapshot create failed: %s", e)
            raise
        finally:
            session.close()


class RiskEventPostgresRepository(_BasePostgresRepository):
    """risk_event 테이블 repository."""

    def create(self, dto: RiskEventCreate) -> int | None:
        session = self._session()
        try:
            m = RiskEventModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                event_type=dto.event_type,
                reason=dto.reason,
                intent_data=dto.intent_data,
                paper_mode=dto.paper_mode,
                event_at=dto.event_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("RiskEvent create failed: %s", e)
            raise
        finally:
            session.close()


class ModelInferenceEventPostgresRepository(_BasePostgresRepository):
    """
    model_inference_event 테이블 repository.
    BUY/SELL 시에만 호출. HOLD 틱은 저장하지 않음 (시세 대량 저장 방지).
    """

    def create(self, dto: ModelInferenceEventCreate) -> int | None:
        session = self._session()
        try:
            m = ModelInferenceEventModel(
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                model_version=dto.model_version,
                feature_set_version=dto.feature_set_version,
                input_snapshot=dto.input_snapshot,
                output_prediction=dto.output_prediction,
                paper_mode=dto.paper_mode,
                inference_at=dto.inference_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("ModelInferenceEvent create failed: %s", e)
            raise
        finally:
            session.close()


class AuditLogPostgresRepository(_BasePostgresRepository):
    """audit_log 테이블 repository."""

    def create(self, dto: AuditLogCreate) -> int | None:
        session = self._session()
        try:
            m = AuditLogModel(
                run_id=dto.run_id,
                correlation_id=dto.correlation_id or "",
                event=dto.event,
                data=dto.data,
                paper_mode=dto.paper_mode,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("AuditLog create failed: %s", e)
            raise
        finally:
            session.close()


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
