"""스토리지 레이어 (order/signal/position/trade/audit)."""

from .interface import (
    OrderStore,
    SignalStore,
    PositionStore,
    TradeStore,
    AuditStore,
    StorageLayer,
)
from .postgres import PostgresStorage

__all__ = [
    "OrderStore",
    "SignalStore",
    "PositionStore",
    "TradeStore",
    "AuditStore",
    "StorageLayer",
    "PostgresStorage",
    "create_storage",
]


def create_storage(config) -> StorageLayer:
    """설정에 따라 스토리지 생성. 초기에는 메모리 PostgresStorage."""
    return PostgresStorage()
