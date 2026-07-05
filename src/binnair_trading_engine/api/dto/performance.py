"""성과 API 응답 DTO."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class PerformanceSummaryDTO:
    user_id: str
    run_id: str | None
    symbol: str | None
    from_at: datetime | None
    to_at: datetime | None
    total_trades: int
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: float
    realized_pnl_total: float
    avg_pnl_per_trade: float
    avg_pnl_pct: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    best_trade_pnl: float | None
    worst_trade_pnl: float | None
    return_pct: float | None
    reference_equity_usdt: float | None


@dataclass
class PerformancePeriodRowDTO:
    period_start: date
    period_label: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl_sum: float
    avg_pnl_pct: float
    return_pct: float | None
    opening_equity_usdt: float | None
    closing_equity_usdt: float | None
