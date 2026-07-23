"""청산 거래 → trade_result DTO 변환 및 PnL 지표 계산."""
from __future__ import annotations

import uuid
from datetime import datetime

from binnair_trading_engine.infra.timezone import ensure_kst, now_kst

from binnair_trading_engine.domain.models import Position
from binnair_trading_engine.infra.persistence.dto import TradeResultCreate


def _ensure_kst(dt: datetime | None) -> datetime:
    return ensure_kst(dt)


def derive_quantity_from_pnl(
    *,
    side: str,
    entry_price: float,
    exit_price: float,
    realized_pnl: float,
) -> float:
    """position_snapshot CLOSED row quantity=0 인 경우 역산."""
    if entry_price <= 0 or exit_price <= 0:
        return 0.0
    if side == "LONG":
        delta = exit_price - entry_price
    else:
        delta = entry_price - exit_price
    if abs(delta) < 1e-12:
        return 0.0
    return abs(realized_pnl / delta)


def win_loss_flags(realized_pnl: float) -> tuple[bool, bool, bool]:
    """is_win, is_loss, is_breakeven."""
    if realized_pnl > 0:
        return True, False, False
    if realized_pnl < 0:
        return False, True, False
    return False, False, True


def compute_pnl_pct(side: str, entry_price: float, exit_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    if side == "LONG":
        return (exit_price - entry_price) / entry_price * 100.0
    return (entry_price - exit_price) / entry_price * 100.0


def build_trade_result_create(
    position: Position,
    *,
    strategy_id: str,
    user_id: str,
    paper_mode: bool,
    correlation_id: str = "",
    position_snapshot_id: int | None = None,
    trade_id: str | None = None,
    min_notional_usdt: float | None = None,
) -> TradeResultCreate | None:
    """CLOSED Position → TradeResultCreate. 필수 필드 없으면 None.

    min_notional_usdt: 진입 명목이 이보다 작으면 dust/유령 청산으로 보고 기록하지 않음.
    """
    if position.status != "CLOSED":
        return None
    realized = float(position.realized_pnl or 0.0)
    entry = float(position.avg_entry_price or 0.0)
    exit_p = float(position.exit_price or 0.0)
    if entry <= 0 or exit_p <= 0:
        return None

    qty = float(position.filled_quantity or 0.0)
    if qty <= 0:
        qty = derive_quantity_from_pnl(
            side=position.side,
            entry_price=entry,
            exit_price=exit_p,
            realized_pnl=realized,
        )
    if qty <= 0:
        return None

    opened = _ensure_kst(position.opened_at)
    closed = _ensure_kst(position.closed_at)
    hold_seconds = max(0, int((closed - opened).total_seconds()))
    notional = entry * qty
    floor = float(min_notional_usdt) if min_notional_usdt is not None else 0.0
    if floor > 0 and notional < floor:
        return None
    pnl_pct = compute_pnl_pct(position.side, entry, exit_p)
    is_win, _, _ = win_loss_flags(realized)

    return TradeResultCreate(
        trade_id=trade_id or str(uuid.uuid4()),
        run_id=position.run_id or "",
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=position.symbol,
        side=position.side,
        quantity=qty,
        entry_price=entry,
        exit_price=exit_p,
        entry_notional_usdt=notional,
        realized_pnl=realized,
        pnl_pct=pnl_pct,
        is_win=is_win,
        exit_reason=position.exit_reason or None,
        correlation_id=correlation_id,
        opened_at=opened,
        closed_at=closed,
        hold_seconds=hold_seconds,
        paper_mode=paper_mode,
        position_snapshot_id=position_snapshot_id,
    )
