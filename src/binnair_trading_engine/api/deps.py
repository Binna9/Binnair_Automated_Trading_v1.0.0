"""
FastAPI 의존성(Dependency) 모듈.

- load_config_path(): config/config.yaml 경로를 CONFIG_PATH에 설정
- get_query_repo(): FlowQueryRepository 싱글톤을 라우트 handler에 주입

왜 필요: 각 API 핸들러가 repository를 직접 만들지 않게 하고,
config·DB 조회 객체를 FastAPI Depends로 공유한다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from binnair_trading_engine.api.repository import FlowQueryRepository
from binnair_trading_engine.config import load_config
from binnair_trading_engine.config.settings import EngineConfig

_query_repo: FlowQueryRepository | None = None
_engine_config: EngineConfig | None = None


def load_config_path() -> None:
    if os.environ.get("CONFIG_PATH"):
        return
    root = Path(__file__).resolve().parents[3]
    for name in ("config/config.yaml", "config.yaml"):
        p = root / name
        if p.exists():
            os.environ["CONFIG_PATH"] = str(p)
            break


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


RepoDep = Annotated[FlowQueryRepository, Depends(get_query_repo)]
ConfigDep = Annotated[EngineConfig, Depends(get_engine_config)]
