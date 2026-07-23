"""dust / 유령 trade_result 차단."""

from __future__ import annotations

from datetime import datetime, timezone

from binnair_trading_engine.domain.models import Position
from binnair_trading_engine.performance.metrics import build_trade_result_create


def _closed_pos(*, qty: float, entry: float, exit_p: float, pnl: float) -> Position:
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    return Position(
        symbol="XRPUSDT",
        quantity=0.0,
        avg_entry_price=entry,
        side="LONG",
        status="CLOSED",
        opened_at=now,
        closed_at=now,
        realized_pnl=pnl,
        exit_price=exit_p,
        exit_reason="STOP_LOSS",
        filled_quantity=qty,
        run_id="prod_timesfm_run",
    )


def test_build_trade_result_skips_dust_notional():
    # ~0.1 XRP * 1.067 ≈ 0.1 USDT — min 5 미만
    pos = _closed_pos(qty=0.1, entry=1.0671, exit_p=1.0602, pnl=-0.00069)
    assert (
        build_trade_result_create(
            pos,
            strategy_id="s",
            user_id="default",
            paper_mode=False,
            min_notional_usdt=5.0,
        )
        is None
    )


def test_build_trade_result_keeps_real_notional():
    pos = _closed_pos(qty=842.6, entry=1.1343, exit_p=1.1297, pnl=-3.88)
    dto = build_trade_result_create(
        pos,
        strategy_id="s",
        user_id="default",
        paper_mode=False,
        min_notional_usdt=5.0,
    )
    assert dto is not None
    assert dto.quantity == 842.6
    assert dto.entry_notional_usdt >= 5.0
