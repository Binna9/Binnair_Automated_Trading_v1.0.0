"""
엔진 매매 이력 REST — `/api/v1/history/*`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from binnair_trading_engine.api.common.parse import parse_datetime
from binnair_trading_engine.api.common.serialize import serialize
from binnair_trading_engine.api.deps import HistoryRepoDep

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("/summary")
def get_history_summary(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None, description="엔진 run_id (권장)"),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None, description="ISO8601 시작 (KST)"),
    to_at: str | None = Query(default=None, description="ISO8601 종료 (KST)"),
) -> dict[str, Any]:
    """현재 run 기준 주문·체결·포지션·PnL 요약."""
    return serialize(
        hist.get_summary(
            user_id=user_id,
            run_id=run_id,
            symbol=symbol,
            from_at=parse_datetime(from_at),
            to_at=parse_datetime(to_at),
        )
    )


@router.get("/orders")
def list_order_history(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    side: str | None = Query(default=None, description="BUY | SELL"),
    fill_status: str | None = Query(
        default=None,
        description="PENDING | FILLED | REJECTED | CANCELLED",
    ),
    from_at: str | None = Query(default=None, description="ISO8601"),
    to_at: str | None = Query(default=None, description="ISO8601"),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    """주문 내역 — order_request + 체결 요약."""
    items = hist.list_orders(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        side=side,
        fill_status=fill_status,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/executions")
def list_execution_history(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    side: str | None = Query(default=None, description="BUY | SELL"),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """체결( fill ) 내역 — order_execution 기준."""
    items = hist.list_executions(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        side=side,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/positions")
def list_position_history(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None, description="OPEN | CLOSED"),
    open_only: bool = Query(
        default=False,
        description="true면 심볼별 최신 OPEN 1건 (현재 보유)",
    ),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """포지션 내역 — position_snapshot."""
    items = hist.list_positions(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        status=status,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        open_only_latest=open_only,
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("/trades")
def list_trade_history(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """청산 완료 거래 (라운드트rip) — trade_result."""
    items = hist.list_trades(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
    )
    return {"items": serialize(items), "count": len(items)}


@router.get("")
def get_history_overview(
    hist: HistoryRepoDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    recent_limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """대시보드용 통합 조회 — summary + 최근 N건."""
    if not run_id:
        raise HTTPException(
            status_code=400,
            detail="run_id is required for history overview",
        )
    dt_from = parse_datetime(from_at)
    dt_to = parse_datetime(to_at)
    common = {
        "user_id": user_id,
        "run_id": run_id,
        "symbol": symbol,
        "from_at": dt_from,
        "to_at": dt_to,
    }
    return {
        "summary": serialize(hist.get_summary(**common)),
        "orders": serialize(hist.list_orders(**common, limit=recent_limit)),
        "executions": serialize(hist.list_executions(**common, limit=recent_limit)),
        "positions": serialize(hist.list_positions(**common, limit=recent_limit)),
        "trades": serialize(hist.list_trades(**common, limit=recent_limit)),
    }
