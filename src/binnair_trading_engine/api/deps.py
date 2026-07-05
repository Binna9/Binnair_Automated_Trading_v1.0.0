"""
FastAPI 의존성(Dependency) — repository·config 싱글톤 주입.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from binnair_trading_engine.api.repositories.flow_repository import FlowQueryRepository
from binnair_trading_engine.api.repositories.history_repository import EngineHistoryRepository
from binnair_trading_engine.api.repositories.performance_repository import (
    PerformanceQueryRepository,
)
from binnair_trading_engine.api.services.history_service import HistoryService
from binnair_trading_engine.config import load_config
from binnair_trading_engine.config.settings import EngineConfig

_query_repo: FlowQueryRepository | None = None
_performance_repo: PerformanceQueryRepository | None = None
_history_repo: EngineHistoryRepository | None = None
_history_service: HistoryService | None = None
_engine_config: EngineConfig | None = None


def load_config_path() -> None:
    """compose env_file 또는 .env.dev / trade.env 로드."""
    from binnair_trading_engine.config.env_loader import load_env_file

    load_env_file()


def get_query_repo() -> FlowQueryRepository:
    global _query_repo
    if _query_repo is None:
        _query_repo = FlowQueryRepository()
    return _query_repo


def get_engine_config() -> EngineConfig:
    global _engine_config
    load_config_path()
    if _engine_config is None:
        _engine_config = load_config()
    return _engine_config


def get_performance_repo() -> PerformanceQueryRepository:
    global _performance_repo
    if _performance_repo is None:
        _performance_repo = PerformanceQueryRepository()
    return _performance_repo


def get_history_repo() -> EngineHistoryRepository:
    global _history_repo
    if _history_repo is None:
        _history_repo = EngineHistoryRepository()
    return _history_repo


def get_history_service() -> HistoryService:
    global _history_service
    if _history_service is None:
        _history_service = HistoryService(get_history_repo(), get_engine_config())
    return _history_service


RepoDep = Annotated[FlowQueryRepository, Depends(get_query_repo)]
PerformanceRepoDep = Annotated[PerformanceQueryRepository, Depends(get_performance_repo)]
HistoryRepoDep = Annotated[EngineHistoryRepository, Depends(get_history_repo)]
HistoryServiceDep = Annotated[HistoryService, Depends(get_history_service)]
ConfigDep = Annotated[EngineConfig, Depends(get_engine_config)]
