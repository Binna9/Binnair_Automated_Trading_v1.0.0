"""
엔진 매매 이력 REST — `/api/v1/history/*`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from binnair_trading_engine.api.common.page import page_response
from binnair_trading_engine.api.common.parse import parse_datetime
from binnair_trading_engine.api.common.serialize import serialize
from binnair_trading_engine.api.deps import HistoryServiceDep

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("/summary")
def get_history_summary(
    hist: HistoryServiceDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None, description="엔진 run_id (권장)"),
    symbol: str | None = Query(default=None),
    from_at: str | None = Query(default=None, description="ISO8601 시작 (KST)"),
    to_at: str | None = Query(default=None, description="ISO8601 종료 (KST)"),
) -> dict[str, Any]:
    """현재 run 기준 주문·체결·포지션·PnL 요약 (정확 COUNT/SUM)."""
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
    hist: HistoryServiceDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    side: str | None = Query(default=None, description="BUY | SELL"),
    fill_status: str | None = Query(
        default=None,
        description="PENDING | FILLED | PARTIAL | REJECTED | CANCELLED",
    ),
    from_at: str | None = Query(default=None, description="ISO8601"),
    to_at: str | None = Query(default=None, description="ISO8601"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """주문 내역 — order_request + 체결 요약."""
    items, total = hist.list_orders(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        side=side,
        fill_status=fill_status,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        offset=offset,
    )
    return page_response(
        serialize(items),
        total_count=total,
        offset=offset,
        limit=limit,
    )


@router.get("/executions")
def list_execution_history(
    hist: HistoryServiceDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    side: str | None = Query(default=None, description="BUY | SELL"),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """체결( fill ) 내역 — order_execution 기준."""
    items, total = hist.list_executions(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        side=side,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        offset=offset,
    )
    return page_response(
        serialize(items),
        total_count=total,
        offset=offset,
        limit=limit,
    )


@router.get("/positions")
def list_position_history(
    hist: HistoryServiceDep,
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
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """포지션 내역 — position_snapshot."""
    items, total = hist.list_positions(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        status=status,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        offset=offset,
        open_only_latest=open_only,
    )
    return page_response(
        serialize(items),
        total_count=total,
        offset=offset,
        limit=limit,
    )


@router.get("/trades")
def list_trade_history(
    hist: HistoryServiceDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    exit_reason: str | None = Query(
        default=None,
        description="TP | SL | SIGNAL | MANUAL | LIQUIDATION 등",
    ),
    is_win: bool | None = Query(default=None, description="true=익절 / false=손절"),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """청산 완료 거래 (라운드트립) — trade_result."""
    items, total = hist.list_trades(
        user_id=user_id,
        run_id=run_id,
        symbol=symbol,
        exit_reason=exit_reason,
        is_win=is_win,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        offset=offset,
    )
    return page_response(
        serialize(items),
        total_count=total,
        offset=offset,
        limit=limit,
    )


@router.get("/equity")
def list_equity_history(
    hist: HistoryServiceDep,
    user_id: str = Query(default="default"),
    run_id: str | None = Query(default=None),
    from_at: str | None = Query(default=None),
    to_at: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """잔고 곡선 — equity_snapshot (시간 오름차순)."""
    items, total = hist.list_equity(
        user_id=user_id,
        run_id=run_id,
        from_at=parse_datetime(from_at),
        to_at=parse_datetime(to_at),
        limit=limit,
        offset=offset,
    )
    return page_response(
        serialize(items),
        total_count=total,
        offset=offset,
        limit=limit,
    )


@router.get("/tick")
def get_tick_detail(
    hist: HistoryServiceDep,
    correlation_id: str = Query(..., description="주문/시그널 추적 ID"),
    user_id: str = Query(default="default"),
) -> dict[str, Any]:
    """correlation_id 기준 판단·주문·체결·청산 묶음."""
    cid = (correlation_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="correlation_id is required")
    return serialize(hist.get_tick_detail(correlation_id=cid, user_id=user_id))


@router.get("")
def get_history_overview(
    hist: HistoryServiceDep,
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
    orders, _ = hist.list_orders(**common, limit=recent_limit, offset=0)
    executions, _ = hist.list_executions(**common, limit=recent_limit, offset=0)
    positions, _ = hist.list_positions(**common, limit=recent_limit, offset=0)
    trades, _ = hist.list_trades(**common, limit=recent_limit, offset=0)
    equity, _ = hist.list_equity(
        user_id=user_id,
        run_id=run_id,
        from_at=dt_from,
        to_at=dt_to,
        limit=recent_limit,
        offset=0,
    )
    return {
        "summary": serialize(hist.get_summary(**common)),
        "orders": serialize(orders),
        "executions": serialize(executions),
        "positions": serialize(positions),
        "trades": serialize(trades),
        "equity": serialize(equity),
    }
