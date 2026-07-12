"""
UI 런타임 제어 DB read/write (API 전용).
"""
from __future__ import annotations

from binnair_trading_engine.infra.persistence.dto import (
    EngineCommandCreate,
    EngineCommandDTO,
    EngineRuntimeStateDTO,
    EngineRuntimeStateUpsert,
)
from binnair_trading_engine.infra.persistence.repositories.postgres import (
    PostgresRepositoryFactory,
)


class RuntimeControlRepository:
    """engine_runtime_state / engine_command 접근."""

    def __init__(self) -> None:
        self._repos = PostgresRepositoryFactory()

    def get_state(self, user_id: str = "default") -> EngineRuntimeStateDTO | None:
        return self._repos.engine_runtime_state.get_by_user_id(user_id)

    def upsert_state(self, dto: EngineRuntimeStateUpsert) -> EngineRuntimeStateDTO:
        return self._repos.engine_runtime_state.upsert(dto)

    def enqueue_command(self, dto: EngineCommandCreate) -> int:
        return self._repos.engine_command.enqueue(dto)

    def list_recent_commands(
        self, user_id: str = "default", limit: int = 5
    ) -> list[EngineCommandDTO]:
        return self._repos.engine_command.get_latest(user_id=user_id, limit=limit)

    def get_engine_run_status(self, run_id: str, user_id: str = "default") -> dict | None:
        return self._repos.engine_run.get_by_run_id(run_id)

    def set_engine_run_trading_active(
        self,
        run_id: str,
        *,
        active: bool,
        user_id: str = "default",
    ) -> None:
        """UI 매매 on/off ↔ engine_run.status (running|paused)."""
        status = "running" if active else "paused"
        self._repos.engine_run.update_status(run_id, status, user_id=user_id)
