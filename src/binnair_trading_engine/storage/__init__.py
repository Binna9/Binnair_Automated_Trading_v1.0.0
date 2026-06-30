"""
엔진 저장 레이어 factory를 제공한다.
설정에 따라 메모리 저장소 또는 Postgres DB 저장소를 생성한다.
"""

from .interface import (
    OrderStore,
    SignalStore,
    PositionStore,
    TradeStore,
    AuditStore,
    StorageLayer,
)
from .postgres import PostgresStorage
from .postgres_db import PostgresDbStorage

__all__ = [
    "OrderStore",
    "SignalStore",
    "PositionStore",
    "TradeStore",
    "AuditStore",
    "StorageLayer",
    "PostgresStorage",
    "PostgresDbStorage",
    "create_storage",
]


def create_storage(config) -> StorageLayer:
    """설정에 따라 스토리지 생성. backend=postgres 시 실제 DB 연동."""
    backend = getattr(config.storage, "backend", "postgres")
    if backend == "memory":
        return PostgresStorage()
    return PostgresDbStorage(config)
