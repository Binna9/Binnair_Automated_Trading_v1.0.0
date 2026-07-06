"""Autopilot 진화 상태 HTTP API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from binnair_trading_engine.api.common.serialize import serialize
from binnair_trading_engine.api.deps import ConfigDep
from binnair_trading_engine.api.services.autopilot_service import get_autopilot_status

router = APIRouter(prefix="/api/v1")


@router.get("/autopilot/status")
def autopilot_status(
    cfg: ConfigDep,
    run_id: str | None = Query(default=None, description="run_id 필터 (미일치 시 available=false)"),
) -> dict[str, Any]:
    """
    Autopilot 레짐·threshold·TP/SL 진화 상태.

    trading-engine이 tick마다 `autopilot_state.json`에 persist한 값을 조회한다.
    """
    return serialize(get_autopilot_status(cfg, run_id=run_id))
