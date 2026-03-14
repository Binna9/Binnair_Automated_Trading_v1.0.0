"""스토리지 인터페이스 정의."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from ..domain.models import (
    AuditLog,
    Order,
    OrderStatus,
    Position,
    Signal,
    Trade,
)

if TYPE_CHECKING:
    from ..domain.models import (
        EngineContext,
        MarketSnapshot,
        OrderIntent,
        Prediction,
        TradeContext,
    )


class OrderStore(Protocol):
    """주문 저장소."""

    def save_order(self, order: Order) -> None: ...
    def get_order(self, order_id: str) -> Order | None: ...
    def get_recent_orders(
        self, run_id: str, symbol: str, limit: int = 20
    ) -> list[Order]: ...
    def update_order_status(self, order_id: str, status: OrderStatus) -> None: ...


class SignalStore(Protocol):
    """시그널 저장소."""

    def save_signal(self, signal: Signal) -> None: ...
    def get_signals(self, run_id: str, symbol: str, limit: int) -> list[Signal]: ...


class PositionStore(Protocol):
    """포지션 저장소."""

    def save_position(self, position: Position) -> None: ...
    def get_positions(self, run_id: str) -> list[Position]: ...


class TradeStore(Protocol):
    """체결/거래 저장소."""

    def save_trade(self, trade: Trade) -> None: ...
    def get_trades(self, run_id: str, symbol: str, since: datetime | None) -> list[Trade]: ...


class AuditStore(Protocol):
    """감사 로그 저장소."""

    def append(self, log: AuditLog) -> None: ...


class StorageLayer(Protocol):
    """엔진용 통합 스토리지 인터페이스."""

    def save_signal(self, signal: Signal) -> None: ...
    def save_order(self, order: Order) -> None: ...
    def get_recent_orders(self, run_id: str, symbol: str, limit: int) -> list[Order]: ...
    def get_positions(self, run_id: str) -> list[Position]: ...
    def get_daily_pnl(self, run_id: str) -> float: ...

    def save_audit(
        self,
        event: str,
        intent: "OrderIntent",
        ctx: "TradeContext",
        reason: str | None = None,
    ) -> None:
        """리스크 거부 등 이벤트 감사 로그 저장."""
        ...

    def save_model_inference(
        self, snapshot: "MarketSnapshot", pred: "Prediction"
    ) -> None:
        """모델 추론 I/O 저장. BUY/SELL 시에만 호출 (HOLD 틱 미저장)."""
        ...

    def record_engine_start(
        self,
        ctx: "EngineContext",
        paper_mode: bool,
        config_snapshot: dict | None = None,
    ) -> None:
        """엔진 시작 시 engine_run 레코드 생성."""
        ...

    def record_engine_stop(self, run_id: str, status: str = "stopped") -> None:
        """엔진 종료 시 engine_run status 업데이트."""
        ...
