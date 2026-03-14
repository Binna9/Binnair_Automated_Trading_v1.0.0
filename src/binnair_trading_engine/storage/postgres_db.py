"""PostgreSQL 실제 DB 연동 스토리지.
infra persistence repository 사용.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from ..config import EngineConfig
from ..domain.models import (
    EngineContext,
    MarketSnapshot,
    OrderSide,
    AuditLog,
    Order,
    OrderIntent,
    OrderStatus,
    Position,
    Prediction,
    Signal,
    Trade,
    TradeContext,
)
from ..infra.persistence.dto import (
    AuditLogCreate,
    EngineRunCreate,
    ModelInferenceEventCreate,
    OrderExecutionCreate,
    OrderRequestCreate,
    SignalEventCreate,
)
from ..infra.persistence.repositories.postgres import PostgresRepositoryFactory
from .interface import (
    AuditStore,
    OrderStore,
    PositionStore,
    SignalStore,
    StorageLayer,
    TradeStore,
)


def _dt(d: datetime | None) -> datetime:
    return d if d else datetime.now(timezone.utc)


def _serialize(o: object) -> dict:
    """dataclass를 JSON-serializable dict로 변환."""
    from dataclasses import is_dataclass

    if is_dataclass(o):
        d = asdict(o)
    elif hasattr(o, "__dict__"):
        d = dict(o.__dict__)
    else:
        return {}
    out = {}
    for k, v in d.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "value"):  # Enum
            out[k] = v.value
        else:
            out[k] = v
    return out


class PostgresDbStorage(
    OrderStore, SignalStore, PositionStore, TradeStore, AuditStore, StorageLayer
):
    """
    실제 PostgreSQL DB 연동 스토리지.
    infra persistence repositories 사용.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._repos = PostgresRepositoryFactory()
        self._paper_mode = config.exchange.paper_mode
        self._run_id = config.run_context.run_id
        self._strategy_id = config.run_context.strategy_id
        self._model_version = config.run_context.model_version
        self._feature_set_version = config.run_context.feature_set_version
        self._order_request_id_cache: dict[str, int] = {}

    def save_order(self, order: Order) -> None:
        req = OrderRequestCreate(
            run_id=order.run_id or self._run_id,
            strategy_id=self._strategy_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            price=order.price,
            correlation_id=order.correlation_id or "",
            paper_mode=self._paper_mode,
            requested_at=_dt(order.created_at),
            order_id=order.order_id,
            client_order_id=order.client_order_id,
        )
        req_id = self._repos.order_request.create(req)
        if req_id and order.order_id:
            self._order_request_id_cache[order.order_id] = req_id

        if order.status == OrderStatus.FILLED:
            ex = OrderExecutionCreate(
                run_id=order.run_id or self._run_id,
                strategy_id=self._strategy_id,
                symbol=order.symbol,
                order_id=order.order_id or "",
                status=order.status.value,
                executed_price=order.price,
                executed_qty=order.quantity,
                raw_response=None,
                paper_mode=self._paper_mode,
                executed_at=_dt(order.updated_at),
                order_request_id=req_id,
            )
            self._repos.order_execution.create(ex)

    def get_order(self, order_id: str) -> Order | None:
        return None

    def get_recent_orders(
        self, run_id: str, symbol: str, limit: int = 50
    ) -> list[Order]:
        return self._repos.order_request.get_recent(run_id, symbol, limit)

    def update_order_status(self, order_id: str, status: OrderStatus) -> None:
        pass

    def save_signal(self, signal: Signal) -> None:
        dto = SignalEventCreate(
            run_id=signal.run_id or self._run_id,
            strategy_id=signal.strategy_id or self._strategy_id,
            symbol=signal.symbol,
            signal_action=signal.action.value,
            confidence=signal.confidence,
            price_hint=signal.price_hint,
            correlation_id="",
            paper_mode=self._paper_mode,
            event_at=_dt(signal.timestamp),
            model_version=signal.model_version or self._model_version,
        )
        self._repos.signal_event.create(dto)

    def save_model_inference(
        self, snapshot: MarketSnapshot, pred: Prediction
    ) -> None:
        dto = ModelInferenceEventCreate(
            run_id=snapshot.run_id or self._run_id,
            strategy_id=self._strategy_id,
            symbol=snapshot.symbol,
            model_version=self._model_version,
            feature_set_version=self._feature_set_version,
            input_snapshot=_serialize(snapshot),
            output_prediction=_serialize(pred),
            paper_mode=self._paper_mode,
            inference_at=_dt(snapshot.timestamp),
        )
        self._repos.model_inference_event.create(dto)

    def get_signals(self, run_id: str, symbol: str, limit: int = 100) -> list[Signal]:
        return []

    def save_position(self, position: Position) -> None:
        pass

    def get_positions(self, run_id: str) -> list[Position]:
        return []

    def save_trade(self, trade: Trade) -> None:
        pass

    def get_trades(
        self, run_id: str, symbol: str, since: datetime | None = None
    ) -> list[Trade]:
        return []

    def append(self, log: AuditLog) -> None:
        pass

    def get_daily_pnl(self, run_id: str) -> float:
        return self._repos.order_execution.get_daily_pnl(run_id)

    def save_audit(
        self,
        event: str,
        intent: OrderIntent,
        ctx: TradeContext,
        reason: str | None = None,
    ) -> None:
        data: dict = {
            "intent_symbol": intent.symbol,
            "intent_side": intent.side.value,
            "intent_qty": intent.quantity,
        }
        if reason:
            data["reason"] = reason
        corr = getattr(ctx, "correlation_id", "") or ""
        dto = AuditLogCreate(
            run_id=ctx.run_id,
            event=event,
            data=data,
            paper_mode=self._paper_mode,
            correlation_id=corr,
        )
        self._repos.audit_log.create(dto)

    def record_engine_start(
        self,
        ctx: EngineContext,
        paper_mode: bool,
        config_snapshot: dict | None = None,
    ) -> None:
        dto = EngineRunCreate(
            run_id=ctx.run_id,
            strategy_id=ctx.strategy_id,
            model_version=ctx.model_version,
            feature_set_version=ctx.feature_set_version,
            version=ctx.version,
            paper_mode=paper_mode,
            started_at=_dt(None),
            config_snapshot=config_snapshot,
        )
        self._repos.engine_run.create(dto)

    def record_engine_stop(self, run_id: str, status: str = "stopped") -> None:
        self._repos.engine_run.update_status(run_id, status)
