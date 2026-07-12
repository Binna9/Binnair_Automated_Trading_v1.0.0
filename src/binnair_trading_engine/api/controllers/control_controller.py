"""UI 런타임 제어 HTTP API — config 저장, start/stop, status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from binnair_trading_engine.api.common.serialize import serialize
from binnair_trading_engine.api.deps import ConfigDep
from binnair_trading_engine.api.services.runtime_control_service import (
    RuntimeControlService,
)
from binnair_trading_engine.config.runtime_config import RuntimeConfigParams

router = APIRouter(prefix="/api/v1/control")
_service = RuntimeControlService()


@router.get("/schema")
def control_schema() -> dict[str, Any]:
    """UI 폼 생성용 파라미터 스키마 + env 전용 키."""
    return serialize(_service.get_schema())


@router.get("/config")
def get_config(
    cfg: ConfigDep,
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """env(L0) + DB(L1) 병합 effective 설정."""
    return serialize(_service.get_effective_config(cfg, user_id=user_id))


@router.put("/config")
def put_config(
    cfg: ConfigDep,
    params: RuntimeConfigParams = Body(...),
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """설정만 저장 (매매 시작 없음)."""
    return serialize(_service.save_config(cfg, params, user_id=user_id))


@router.post("/start")
def start_trading(
    cfg: ConfigDep,
    params: RuntimeConfigParams = Body(default_factory=RuntimeConfigParams),
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """설정 저장 + trading_enabled + start 명령 enqueue."""
    return serialize(_service.start(cfg, params, user_id=user_id))


@router.post("/stop")
def stop_trading(
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """trading 중지 명령 enqueue."""
    return serialize(_service.stop(user_id=user_id))


@router.get("/status")
def control_status(
    cfg: ConfigDep,
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """trading_enabled, config_version, engine_run, 최근 명령."""
    return serialize(_service.get_status(cfg, user_id=user_id))
