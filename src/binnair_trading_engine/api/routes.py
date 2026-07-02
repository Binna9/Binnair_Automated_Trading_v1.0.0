"""
HTTP URL ↔ handler 정의.

GET /api/v1/dashboard, /positions, /flow/timeline 등 엔드포인트.
쿼리 파라미터(user_id, run_id, symbol)를 받아 repository 호출 후 JSON 반환.

왜 필요: Postman/프론트가 호출하는 URL 계약(URL, method, params)만 담당.
DB·비즈니스 로직은 repository에 위임한다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from binnair_trading_engine.api.deps import RepoDep
from binnair_trading_engine.api.serialize import serialize

router = APIRouter(prefix="/api/v1")


@router.get("/dashboard")
def get_dashboard(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
) -> dict[str, Any]:
    return serialize(
        repo.get_dashboard(user_id=user_id, run_id=run_id, symbol=symbol)
    )


@router.get("/engine-runs")
def list_engine_runs(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    runs = repo.list_engine_runs(user_id=user_id, limit=limit, status=status)
    return {"items": serialize(runs), "count": len(runs)}


@router.get("/engine-runs/{run_id}")
def get_engine_run(
    run_id: str,
    repo: RepoDep,
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    run = repo.get_engine_run(run_id, user_id=user_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return serialize(run)


@router.get("/positions/open")
def list_open_positions(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    symbol: str | None = Query(default=None),
) -> dict[str, Any]:
    items = repo.list_open_positions(user_id=user_id, symbol=symbol)
    return {"items": serialize(items), "count": len(items)}


@router.get("/positions")
def list_positions(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None, description="OPEN | CLOSED"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.list_positions(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        status=status,
        limit=limit,
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/signals")
def list_signals(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.list_signals(
        user_id=user_id, run_id=run_id, symbol=symbol, limit=limit
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/inferences")
def list_inferences(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.list_inferences(
        user_id=user_id, run_id=run_id, symbol=symbol, limit=limit
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/orders")
def list_orders(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    items = repo.list_order_flows(
        user_id=user_id, run_id=run_id, symbol=symbol, limit=limit
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/audit-logs")
def list_audit_logs(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.list_audit_logs(user_id=user_id, run_id=run_id, limit=limit)
    return {"items": serialize(items), "count": len(items)}


@router.get("/flow/timeline")
def get_flow_timeline(
    repo: RepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.get_flow_timeline(
        user_id=user_id, run_id=run_id, symbol=symbol, limit=limit
    )
    return {"items": serialize(items), "count": len(items)}
