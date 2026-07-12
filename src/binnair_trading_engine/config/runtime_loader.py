"""
DB engine_runtime_state(L1)를 env 기반 EngineConfig(L0)에 병합한다.
"""
from __future__ import annotations

from binnair_trading_engine.config.runtime_config import merge_runtime_config
from binnair_trading_engine.config.settings import EngineConfig
from binnair_trading_engine.infra.persistence.dto import EngineRuntimeStateDTO
from binnair_trading_engine.infra.persistence.repositories.postgres import (
    PostgresRepositoryFactory,
)


def load_runtime_state(user_id: str = "default") -> EngineRuntimeStateDTO | None:
    """Postgres engine_runtime_state 조회. backend!=postgres면 None."""
    return PostgresRepositoryFactory().engine_runtime_state.get_by_user_id(user_id)


def apply_runtime_overlay(
    base: EngineConfig,
    *,
    user_id: str = "default",
) -> tuple[EngineConfig, EngineRuntimeStateDTO | None]:
    """
    DB에 저장된 L1 설정이 있으면 env 위에 병합.
    없으면 base 그대로 반환.
    """
    state = load_runtime_state(user_id)
    if state is None or not state.config_json:
        return base, state
    merged = merge_runtime_config(base, state.config_json)
    return merged, state
