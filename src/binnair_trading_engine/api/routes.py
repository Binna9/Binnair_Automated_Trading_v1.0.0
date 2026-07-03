"""
HTTP URL ↔ handler 정의.

GET /api/v1/dashboard, /positions, /flow/timeline 등 엔드포인트.
쿼리 파라미터(user_id, run_id, symbol)를 받아 repository 호출 후 JSON 반환.

왜 필요: Postman/프론트가 호출하는 URL 계약(URL, method, params)만 담당.
DB·비즈니스 로직은 repository에 위임한다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from binnair_trading_engine.api.deps import ConfigDep, PerformanceRepoDep, RepoDep
from binnair_trading_engine.api.serialize import serialize
from binnair_trading_engine.api.wallet_service import fetch_wallet_info

router = APIRouter(prefix="/api/v1")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


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


@router.get("/account/wallet")
def get_account_wallet(cfg: ConfigDep) -> dict[str, Any]:
    """
    config.exchange(testnet) 지갑·포지션 조회.
    엔진 sizing에 쓰는 USDT availableBalance와 주문 가능 여부 진단 포함.
    """
    return fetch_wallet_info(cfg)


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


@router.get("/performance/summary")
def get_performance_summary(
    perf: PerformanceRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None, description="ISO8601 시작"),
    to_at: str | None = Query(default=None, description="ISO8601 종료"),
) -> dict[str, Any]:
    """기간별 성과 요약 (승률·PnL·수익률)."""
    return serialize(
        perf.get_summary(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=_parse_datetime(from_at),
            to_at=_parse_datetime(to_at),
        )
    )


@router.get("/performance/periods")
def get_performance_periods(
    perf: PerformanceRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    granularity: str = Query(default="day", description="day | week | month"),
    from_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    to_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=90, ge=1, le=366),
) -> dict[str, Any]:
    """일/주/월 단위 성과 시계열."""
    if granularity not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="granularity must be day|week|month")
    items = perf.list_periods(
        user_id=user_id,
        run_id=run_id,
        granularity=granularity,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        limit=limit,
    )
    return {"granularity": granularity, "items": serialize(items), "count": len(items)}


@router.get("/performance/trades")
def list_performance_trades(
    perf: PerformanceRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """청산 완료 거래 목록 (trade_result)."""
    items = perf.list_trades(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        from_at=_parse_datetime(from_at),
        to_at=_parse_datetime(to_at),
        limit=limit,
    )
    return {"items": serialize(items), "count": len(items)}
