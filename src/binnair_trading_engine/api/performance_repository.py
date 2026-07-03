"""
성과(PnL·승률) DB 조회 (read-only).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import case, func, select, text

from binnair_trading_engine.api.db import get_db_session
from binnair_trading_engine.api.mappers import to_performance_daily_dto, to_trade_result_dto
from binnair_trading_engine.infra.persistence.dto import PerformanceDailyDTO, TradeResultDTO
from binnair_trading_engine.infra.persistence.models import (
    EquitySnapshotModel,
    PerformanceDailyModel,
    TradeResultModel,
)


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


class PerformanceQueryRepository:
    """trade_result / performance_daily 조회."""

    def _trade_filters(
        self,
        stmt,
        *,
        user_id: str,
        run_id: str | None,
        symbol: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
    ):
        stmt = stmt.where(TradeResultModel.user_id == user_id)
        if run_id:
            stmt = stmt.where(TradeResultModel.run_id == run_id)
        if symbol:
            stmt = stmt.where(TradeResultModel.symbol == symbol)
        if from_at:
            stmt = stmt.where(TradeResultModel.closed_at >= from_at)
        if to_at:
            stmt = stmt.where(TradeResultModel.closed_at <= to_at)
        return stmt

    def list_trades(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
    ) -> list[TradeResultDTO]:
        session = get_db_session()
        try:
            stmt = select(TradeResultModel).order_by(TradeResultModel.closed_at.desc())
            stmt = self._trade_filters(
                stmt,
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
            )
            rows = session.execute(stmt.limit(max(1, min(limit, 500)))).scalars().all()
            return [to_trade_result_dto(r) for r in rows]
        finally:
            session.close()

    def get_summary(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        symbol: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> PerformanceSummaryDTO:
        session = get_db_session()
        try:
            stmt = select(
                func.count(TradeResultModel.id),
                func.coalesce(
                    func.sum(case((TradeResultModel.is_win.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((TradeResultModel.realized_pnl < 0, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((TradeResultModel.realized_pnl == 0, 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(TradeResultModel.realized_pnl), 0.0),
                func.coalesce(func.avg(TradeResultModel.realized_pnl), 0.0),
                func.coalesce(func.avg(TradeResultModel.pnl_pct), 0.0),
                func.coalesce(
                    func.sum(
                        case(
                            (TradeResultModel.realized_pnl > 0, TradeResultModel.realized_pnl),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (TradeResultModel.realized_pnl < 0, -TradeResultModel.realized_pnl),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.max(TradeResultModel.realized_pnl),
                func.min(TradeResultModel.realized_pnl),
            )
            stmt = self._trade_filters(
                stmt,
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
            )
            row = session.execute(stmt).one()
            total, wins, losses, breakeven, pnl_sum, avg_pnl, avg_pct, gross_profit, gross_loss, best, worst = row
            total = int(total or 0)
            wins = int(wins or 0)
            losses = int(losses or 0)
            breakeven = int(breakeven or 0)
            pnl_sum = float(pnl_sum or 0.0)
            gross_profit = float(gross_profit or 0.0)
            gross_loss = float(gross_loss or 0.0)
            win_rate = (wins / total) if total > 0 else 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

            ref_equity = None
            return_pct = None
            if run_id:
                eq_stmt = (
                    select(EquitySnapshotModel.equity_usdt)
                    .where(
                        EquitySnapshotModel.user_id == user_id,
                        EquitySnapshotModel.run_id == run_id,
                    )
                    .order_by(EquitySnapshotModel.snapshot_at.asc())
                    .limit(1)
                )
                ref_equity = session.execute(eq_stmt).scalar_one_or_none()
                if ref_equity and ref_equity > 0:
                    return_pct = pnl_sum / float(ref_equity) * 100.0

            return PerformanceSummaryDTO(
                user_id=user_id,
                run_id=run_id,
                symbol=symbol,
                from_at=from_at,
                to_at=to_at,
                total_trades=total,
                win_count=wins,
                loss_count=losses,
                breakeven_count=breakeven,
                win_rate=win_rate,
                realized_pnl_total=pnl_sum,
                avg_pnl_per_trade=float(avg_pnl or 0.0),
                avg_pnl_pct=float(avg_pct or 0.0),
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                profit_factor=profit_factor,
                best_trade_pnl=float(best) if best is not None else None,
                worst_trade_pnl=float(worst) if worst is not None else None,
                return_pct=return_pct,
                reference_equity_usdt=float(ref_equity) if ref_equity is not None else None,
            )
        finally:
            session.close()

    def list_daily(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 90,
    ) -> list[PerformanceDailyDTO]:
        session = get_db_session()
        try:
            stmt = select(PerformanceDailyModel).order_by(PerformanceDailyModel.period_date.desc())
            stmt = stmt.where(PerformanceDailyModel.user_id == user_id)
            if run_id:
                stmt = stmt.where(PerformanceDailyModel.run_id == run_id)
            if from_date:
                stmt = stmt.where(PerformanceDailyModel.period_date >= from_date)
            if to_date:
                stmt = stmt.where(PerformanceDailyModel.period_date <= to_date)
            rows = session.execute(stmt.limit(max(1, min(limit, 366)))).scalars().all()
            return [to_performance_daily_dto(r) for r in rows]
        finally:
            session.close()

    def list_periods(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        granularity: str = "day",
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 90,
    ) -> list[PerformancePeriodRowDTO]:
        """granularity: day | week | month."""
        if granularity == "day":
            dailies = self.list_daily(
                user_id=user_id,
                run_id=run_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
            )
            rows: list[PerformancePeriodRowDTO] = []
            for d in sorted(dailies, key=lambda x: x.period_date):
                tc = d.trade_count
                wr = (d.win_count / tc) if tc > 0 else 0.0
                ret = None
                if d.opening_equity_usdt and d.opening_equity_usdt > 0:
                    ret = d.realized_pnl_sum / d.opening_equity_usdt * 100.0
                rows.append(
                    PerformancePeriodRowDTO(
                        period_start=d.period_date,
                        period_label=d.period_date.isoformat(),
                        trade_count=tc,
                        win_count=d.win_count,
                        loss_count=d.loss_count,
                        win_rate=wr,
                        realized_pnl_sum=d.realized_pnl_sum,
                        avg_pnl_pct=d.avg_pnl_pct,
                        return_pct=ret,
                        opening_equity_usdt=d.opening_equity_usdt,
                        closing_equity_usdt=d.closing_equity_usdt,
                    )
                )
            return rows

        session = get_db_session()
        try:
            schema = TradeResultModel.__table__.schema or "trade"
            if granularity == "week":
                bucket = "date_trunc('week', closed_at)::date"
                label = "to_char(date_trunc('week', closed_at), 'IYYY-\"W\"IW')"
            elif granularity == "month":
                bucket = "date_trunc('month', closed_at)::date"
                label = "to_char(date_trunc('month', closed_at), 'YYYY-MM')"
            else:
                raise ValueError(f"unsupported granularity: {granularity}")

            sql = f"""
                SELECT
                    {bucket} AS period_start,
                    {label} AS period_label,
                    COUNT(*) AS trade_count,
                    SUM(CASE WHEN is_win THEN 1 ELSE 0 END) AS win_count,
                    SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) AS loss_count,
                    COALESCE(SUM(realized_pnl), 0) AS realized_pnl_sum,
                    COALESCE(AVG(pnl_pct), 0) AS avg_pnl_pct
                FROM "{schema}".trade_result
                WHERE user_id = :user_id
            """
            params: dict = {"user_id": user_id}
            if run_id:
                sql += " AND run_id = :run_id"
                params["run_id"] = run_id
            if from_date:
                sql += " AND closed_at >= :from_at"
                params["from_at"] = datetime.combine(
                    from_date, datetime.min.time(), tzinfo=timezone.utc
                )
            if to_date:
                sql += " AND closed_at < :to_at"
                next_day = datetime.combine(to_date, datetime.min.time(), tzinfo=timezone.utc)
                params["to_at"] = next_day.replace(hour=23, minute=59, second=59)
            sql += f" GROUP BY {bucket}, {label} ORDER BY period_start DESC LIMIT :lim"
            params["lim"] = max(1, min(limit, 366))

            result = session.execute(text(sql), params)
            out: list[PerformancePeriodRowDTO] = []
            for r in result:
                tc = int(r.trade_count or 0)
                wins = int(r.win_count or 0)
                out.append(
                    PerformancePeriodRowDTO(
                        period_start=r.period_start,
                        period_label=r.period_label,
                        trade_count=tc,
                        win_count=wins,
                        loss_count=int(r.loss_count or 0),
                        win_rate=(wins / tc) if tc > 0 else 0.0,
                        realized_pnl_sum=float(r.realized_pnl_sum or 0.0),
                        avg_pnl_pct=float(r.avg_pnl_pct or 0.0),
                        return_pct=None,
                        opening_equity_usdt=None,
                        closing_equity_usdt=None,
                    )
                )
            return list(reversed(out))
        finally:
            session.close()
