"""
메모리 기반 MVP 저장소 구현이다.
PostgresStorage 이름을 유지하지만 backend=memory에서 테스트용으로 사용한다.
"""

from datetime import datetime, timedelta

from binnair_trading_engine.infra.timezone import kst_today_start

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
from .interface import (
    AuditStore,
    OrderStore,
    PositionStore,
    SignalStore,
    StorageLayer,
    TradeStore,
)


class PostgresStorage(
    OrderStore, SignalStore, PositionStore, TradeStore, AuditStore, StorageLayer
):
    """
    PostgreSQL 기반 통합 스토리지.
    초기에는 메모리 저장으로 동작하며, 실제 DB 연결은 추후 구현.
    """

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._signals: list[Signal] = []
        self._positions: list[Position] = []
        self._trades: list[Trade] = []
        self._audit: list[AuditLog] = []

    def save_order(self, order: Order) -> None:
        key = order.order_id or str(id(order))
        self._orders[key] = order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_recent_orders(
        self, run_id: str, symbol: str, limit: int = 50
    ) -> list[Order]:
        out = [
            o
            for o in self._orders.values()
            if o.run_id == run_id and o.symbol == symbol
        ]
        out.sort(key=lambda o: o.created_at or datetime.min, reverse=True)
        return out[:limit]

    def update_order_status(self, order_id: str, status: OrderStatus) -> None:
        if o := self._orders.get(order_id):
            self._orders[order_id] = Order(
                **{**o.__dict__, "status": status}  # type: ignore
            )

    def save_signal(self, signal: Signal) -> None:
        self._signals.append(signal)

    def save_model_inference(
        self, snapshot: MarketSnapshot, pred: Prediction
    ) -> None:
        """BUY/SELL 시에만 호출. 현재는 no-op (infra persistence 연동 시 구현)."""
        pass

    def get_signals(
        self, run_id: str, symbol: str, limit: int = 100
    ) -> list[Signal]:
        out = [s for s in self._signals if s.run_id == run_id and s.symbol == symbol]
        return out[-limit:]

    def save_position(self, position: Position) -> None:
        existing = [p for p in self._positions if p.position_id != position.position_id]
        self._positions = existing + [position]

    def get_positions(self, run_id: str) -> list[Position]:
        return [p for p in self._positions if p.run_id == run_id]

    def save_trade(self, trade: Trade) -> None:
        self._trades.append(trade)

    def get_trades(
        self, run_id: str, symbol: str, since: datetime | None = None
    ) -> list[Trade]:
        out = [t for t in self._trades if t.run_id == run_id and t.symbol == symbol]
        if since:
            out = [t for t in out if t.executed_at >= since]
        return out

    def append(self, log: AuditLog) -> None:
        self._audit.append(log)

    def get_daily_pnl(self, run_id: str) -> float:
        """당일 실현손익. sell +, buy - 로 대략 계산."""
        today = kst_today_start()
        pnl = 0.0
        for t in self._trades:
            if t.run_id != run_id or t.executed_at < today:
                continue
            sign = 1.0 if t.side == OrderSide.SELL else -1.0
            pnl += sign * t.price * t.quantity - t.commission
        return pnl

    def save_audit(
        self,
        event: str,
        intent: OrderIntent,
        ctx: TradeContext,
        reason: str | None = None,
        extra_data: dict | None = None,
    ) -> None:
        data: dict = {
            "intent_symbol": intent.symbol,
            "intent_side": intent.side.value,
            "intent_qty": intent.quantity,
        }
        if reason:
            data["reason"] = reason
        if extra_data:
            data.update(extra_data)
        log = AuditLog(
            event=event,
            run_id=ctx.run_id,
            correlation_id=getattr(ctx, "correlation_id", "") or "",
            data=data,
        )
        self.append(log)

    def record_engine_start(
        self,
        ctx: EngineContext,
        paper_mode: bool,
        config_snapshot: dict | None = None,
        trading_enabled: bool = False,
    ) -> None:
        pass

    def record_engine_stop(self, run_id: str, status: str = "stopped") -> None:
        pass
