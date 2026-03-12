"""State manager - 장애 복구 및 상태 일관성 관리를 위한 모듈."""

from binnair_trading_engine.state.manager import StateManager

__all__ = ["StateManager", "create_state_manager"]


def create_state_manager(config) -> StateManager:
    """설정에 따라 StateManager 생성."""
    from binnair_trading_engine.config.settings import EngineConfig
    cfg: EngineConfig = config
    path = cfg.state_persist_path
    return StateManager(persist_path=path)
