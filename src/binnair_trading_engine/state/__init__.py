"""
엔진 상태 관리 패키지 공개 API다.
StateManager와 create_state_manager를 제공한다.
"""

from binnair_trading_engine.state.manager import StateManager

__all__ = ["StateManager", "create_state_manager"]


def create_state_manager(config) -> StateManager:
    """설정에 따라 StateManager 생성."""
    from binnair_trading_engine.config.settings import EngineConfig
    cfg: EngineConfig = config
    path = cfg.state_persist_path
    return StateManager(persist_path=path)
