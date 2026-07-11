"""
Postgres 기반 repository 구현체 모음이다.
DTO를 SQLAlchemy ORM으로 변환해 insert, upsert, query를 수행한다.
"""

from __future__ import annotations

import logging
from datetime import datetime

from binnair_trading_engine.infra.timezone import ensure_kst, kst_today_start, now_kst
from typing import TYPE_CHECKING

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from binnair_trading_engine.infra.persistence.dto import (
    AuditLogCreate,
    EngineRunCreate,
    EngineRunStatus,
    ModelInferenceEventCreate,
    OhlcvCandleCreate,
    OrderExecutionCreate,
    OrderRequestCreate,
    PositionSnapshotCreate,
    RiskEventCreate,
    SignalEventCreate,
    StrategyConfigSnapshotCreate,
    TradeResultCreate,
    EquitySnapshotCreate,
)
from binnair_trading_engine.infra.persistence.models import (
    AuditLogModel,
    EngineRunModel,
    ModelInferenceEventModel,
    OhlcvCandleModel,
    OrderExecutionModel,
    OrderRequestModel,
    PositionSnapshotModel,
    RiskEventModel,
    SignalEventModel,
    StrategyConfigSnapshotModel,
    TradeResultModel,
    PerformanceDailyModel,
    EquitySnapshotModel,
)
from binnair_trading_engine.infra.persistence.session import get_engine, get_session_factory

from binnair_trading_engine.performance.metrics import win_loss_flags

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import Order

logger = logging.getLogger(__name__)

_session_factory_cache = None


def _get_session_factory():
    global _session_factory_cache
    if _session_factory_cache is None:
        _session_factory_cache = get_session_factory(get_engine())
    return _session_factory_cache


def _ensure_kst(dt: datetime | None) -> datetime:
    return ensure_kst(dt)


def _session_scope():
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class _BasePostgresRepository:
    """공통 세션 팩토리."""

    def _session(self) -> Session:
        return _get_session_factory()()


class OhlcvCandlePostgresRepository(_BasePostgresRepository):
    """ohlcv_candle 테이블 repository."""

    def upsert_many(self, candles: list[OhlcvCandleCreate]) -> int:
        if not candles:
            return 0

        rows = [
            {
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "open_time": _ensure_kst(c.open_time),
                "close_time": _ensure_kst(c.close_time),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "quote_volume": c.quote_volume,
                "trade_count": c.trade_count,
            }
            for c in candles
        ]

        session = self._session()
        try:
            stmt = insert(OhlcvCandleModel).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "open_time"],
                set_={
                    "close_time": stmt.excluded.close_time,
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "quote_volume": stmt.excluded.quote_volume,
                    "trade_count": stmt.excluded.trade_count,
                },
            )
            result = session.execute(stmt)
            session.commit()
            rowcount = result.rowcount
            return int(rowcount) if rowcount is not None and rowcount >= 0 else len(rows)
        except Exception as e:
            session.rollback()
            logger.exception("OhlcvCandle upsert_many failed: %s", e)
            raise
        finally:
            session.close()

    def get_recent_closes(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[float]:
        if limit <= 0:
            return []

        session = self._session()
        try:
            stmt = (
                select(OhlcvCandleModel.close)
                .where(
                    OhlcvCandleModel.symbol == symbol,
                    OhlcvCandleModel.timeframe == timeframe,
                )
                .order_by(OhlcvCandleModel.open_time.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [float(v) for v in reversed(rows)]
        finally:
            session.close()

    def get_recent_ohlc(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[tuple[float, float, float]]:
        """최근 (high, low, close) 튜플, 오래된 순. True Range/ATR 계산용."""
        if limit <= 0:
            return []

        session = self._session()
        try:
            stmt = (
                select(
                    OhlcvCandleModel.high,
                    OhlcvCandleModel.low,
                    OhlcvCandleModel.close,
                )
                .where(
                    OhlcvCandleModel.symbol == symbol,
                    OhlcvCandleModel.timeframe == timeframe,
                )
                .order_by(OhlcvCandleModel.open_time.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).all()
            return [(float(h), float(l), float(c)) for h, l, c in reversed(rows)]
        finally:
            session.close()

    def get_latest_candle_open_time(
        self,
        symbol: str,
        timeframe: str,
    ):
        session = self._session()
        try:
            stmt = (
                select(OhlcvCandleModel.open_time)
                .where(
                    OhlcvCandleModel.symbol == symbol,
                    OhlcvCandleModel.timeframe == timeframe,
                )
                .order_by(OhlcvCandleModel.open_time.desc())
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()
        finally:
            session.close()


class EngineRunPostgresRepository(_BasePostgresRepository):
    """engine_run 테이블 repository."""

    def create(self, dto: EngineRunCreate) -> str | None:
        session = self._session()
        try:
            existing = session.execute(
                select(EngineRunModel).where(
                    EngineRunModel.run_id == dto.run_id,
                    EngineRunModel.user_id == (dto.user_id or "default"),
                )
            ).scalars().first()
            if existing:
                existing.status = "running"
                existing.started_at = dto.started_at
                existing.stopped_at = None
                existing.strategy_id = dto.strategy_id
                existing.model_version = dto.model_version
                existing.feature_set_version = dto.feature_set_version
                existing.version = dto.version
                existing.paper_mode = dto.paper_mode
                existing.config_snapshot = dto.config_snapshot
                session.commit()
                return dto.run_id
            m = EngineRunModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                model_version=dto.model_version,
                feature_set_version=dto.feature_set_version,
                version=dto.version,
                paper_mode=dto.paper_mode,
                status="running",
                started_at=dto.started_at,
                config_snapshot=dto.config_snapshot,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return dto.run_id
        except Exception as e:
            session.rollback()
            logger.exception("EngineRun create failed: %s", e)
            raise
        finally:
            session.close()

    def update_status(
        self, run_id: str, status: EngineRunStatus, user_id: str = "default"
    ) -> None:
        session = self._session()
        try:
            stmt = (
                select(EngineRunModel)
                .where(
                    EngineRunModel.run_id == run_id,
                    EngineRunModel.user_id == user_id,
                )
            )
            row = session.execute(stmt).scalars().first()
            if row:
                row.status = status
                row.stopped_at = now_kst()
                session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("EngineRun update_status failed: %s", e)
            raise
        finally:
            session.close()

    def get_by_run_id(self, run_id: str) -> dict | None:
        session = self._session()
        try:
            stmt = select(EngineRunModel).where(EngineRunModel.run_id == run_id)
            row = session.execute(stmt).scalars().first()
            return row.__dict__ if row else None
        finally:
            session.close()


class StrategyConfigSnapshotPostgresRepository(_BasePostgresRepository):
    """strategy_config_snapshot 테이블 repository."""

    def create(self, dto: StrategyConfigSnapshotCreate) -> int | None:
        session = self._session()
        try:
            m = StrategyConfigSnapshotModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                snapshot_at=dto.snapshot_at,
                config_json=dto.config_json,
                paper_mode=dto.paper_mode,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("StrategyConfigSnapshot create failed: %s", e)
            raise
        finally:
            session.close()


class SignalEventPostgresRepository(_BasePostgresRepository):
    """signal_event 테이블 repository."""

    def create(self, dto: SignalEventCreate) -> int | None:
        session = self._session()
        try:
            m = SignalEventModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                signal_action=dto.signal_action,
                confidence=dto.confidence,
                price_hint=dto.price_hint,
                correlation_id=dto.correlation_id or "",
                paper_mode=dto.paper_mode,
                event_at=dto.event_at,
                timeframe=dto.timeframe,
                model_version=dto.model_version or "",
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("SignalEvent create failed: %s", e)
            raise
        finally:
            session.close()


class OrderRequestPostgresRepository(_BasePostgresRepository):
    """order_request 테이블 repository."""

    def create(self, dto: OrderRequestCreate) -> int | None:
        session = self._session()
        try:
            m = OrderRequestModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                side=dto.side,
                order_type=dto.order_type,
                quantity=dto.quantity,
                price=dto.price,
                stop_price=dto.stop_price,
                reduce_only=dto.reduce_only,
                position_side=dto.position_side,
                correlation_id=dto.correlation_id or "",
                paper_mode=dto.paper_mode,
                requested_at=dto.requested_at,
                order_id=dto.order_id,
                client_order_id=dto.client_order_id,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("OrderRequest create failed: %s", e)
            raise
        finally:
            session.close()

    def get_recent(
        self, run_id: str, symbol: str, limit: int = 50, user_id: str = "default"
    ) -> list["Order"]:
        from binnair_trading_engine.domain.models import (
            Order,
            OrderSide,
            OrderStatus,
            OrderType,
        )

        session = self._session()
        try:
            stmt = (
                select(OrderRequestModel)
                .where(
                    OrderRequestModel.run_id == run_id,
                    OrderRequestModel.symbol == symbol,
                    OrderRequestModel.user_id == user_id,
                )
                .order_by(OrderRequestModel.requested_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                Order(
                    symbol=r.symbol,
                    side=OrderSide(r.side),
                    order_type=OrderType(r.order_type),
                    quantity=r.quantity,
                    price=r.price,
                    stop_price=r.stop_price,
                    status=OrderStatus.PENDING,
                    order_id=r.order_id or "",
                    client_order_id=r.client_order_id,
                    run_id=r.run_id,
                    correlation_id=r.correlation_id or "",
                    reduce_only=r.reduce_only,
                    position_side=r.position_side,
                    created_at=_ensure_kst(r.requested_at),
                    updated_at=_ensure_kst(r.requested_at),
                )
                for r in rows
            ]
        finally:
            session.close()


class OrderExecutionPostgresRepository(_BasePostgresRepository):
    """order_execution 테이블 repository."""

    def create(self, dto: OrderExecutionCreate) -> int | None:
        session = self._session()
        try:
            m = OrderExecutionModel(
                user_id=dto.user_id or "default",
                order_request_id=dto.order_request_id,
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                order_id=dto.order_id,
                status=dto.status,
                executed_price=dto.executed_price,
                executed_quantity=dto.executed_qty,
                stop_price=dto.stop_price,
                reduce_only=dto.reduce_only,
                position_side=dto.position_side,
                raw_response=dto.raw_response,
                paper_mode=dto.paper_mode,
                executed_at=dto.executed_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("OrderExecution create failed: %s", e)
            raise
        finally:
            session.close()

    def get_daily_pnl(self, run_id: str, user_id: str = "default") -> float:
        """당일 실현손익 (SELL +, BUY -). order_request와 join해 side 사용."""
        session = self._session()
        try:
            today = kst_today_start()
            schema = OrderExecutionModel.__table__.schema or "trade"
            stmt = text(f"""
                SELECT req.side, ex.executed_price, ex.executed_quantity
                FROM "{schema}".order_execution ex
                JOIN "{schema}".order_request req ON ex.order_request_id = req.id
                WHERE ex.run_id = :run_id AND ex.user_id = :user_id AND ex.executed_at >= :today
            """)
            result = session.execute(
                stmt, {"run_id": run_id, "user_id": user_id, "today": today}
            )
            pnl = 0.0
            for row in result:
                side, price, qty = row[0], row[1] or 0.0, row[2] or 0.0
                sign = 1.0 if side == "SELL" else -1.0
                pnl += sign * price * qty
            return pnl
        finally:
            session.close()


class PositionSnapshotPostgresRepository(_BasePostgresRepository):
    """position_snapshot 테이블 repository."""

    def create(self, dto: PositionSnapshotCreate) -> int | None:
        session = self._session()
        try:
            m = PositionSnapshotModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                side=dto.side,
                quantity=dto.quantity,
                avg_entry_price=dto.avg_entry_price,
                tp_price=dto.tp_price,
                sl_price=dto.sl_price,
                status=dto.status,
                unrealized_pnl=dto.unrealized_pnl,
                realized_pnl=dto.realized_pnl,
                exit_reason=dto.exit_reason,
                exit_price=dto.exit_price,
                opened_at=dto.opened_at,
                closed_at=dto.closed_at,
                paper_mode=dto.paper_mode,
                snapshot_at=dto.snapshot_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("PositionSnapshot create failed: %s", e)
            raise
        finally:
            session.close()

    def get_latest_open_per_symbol(
        self, symbols: list[str], user_id: str = "default"
    ) -> list[dict]:
        """
        심볼별 **최신** position_snapshot이 OPEN일 때만 반환.

        append-only 이력이므로 status=OPEN 필터만 쓰면
        CLOSED 이후에도 과거 OPEN 행이 복구되는 문제가 있다.
        """
        if not symbols:
            return []
        session = self._session()
        try:
            schema = PositionSnapshotModel.__table__.schema or "trade"
            stmt = text(f"""
                SELECT id, run_id, strategy_id, symbol, side, quantity, avg_entry_price,
                       tp_price, sl_price, status, opened_at, snapshot_at
                FROM (
                    SELECT DISTINCT ON (symbol)
                        id, run_id, strategy_id, symbol, side, quantity, avg_entry_price,
                        tp_price, sl_price, status, opened_at, snapshot_at
                    FROM "{schema}".position_snapshot
                    WHERE symbol IN :symbols AND user_id = :user_id
                    ORDER BY symbol, snapshot_at DESC
                ) latest
                WHERE latest.status = 'OPEN' AND latest.quantity > 0
            """).bindparams(bindparam("symbols", expanding=True))
            result = session.execute(stmt, {"symbols": symbols, "user_id": user_id})
            rows = result.fetchall()
            cols = result.keys()
            return [dict(zip(cols, r)) for r in rows]
        finally:
            session.close()


class RiskEventPostgresRepository(_BasePostgresRepository):
    """risk_event 테이블 repository."""

    def create(self, dto: RiskEventCreate) -> int | None:
        session = self._session()
        try:
            m = RiskEventModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                event_type=dto.event_type,
                reason=dto.reason,
                intent_data=dto.intent_data,
                paper_mode=dto.paper_mode,
                event_at=dto.event_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("RiskEvent create failed: %s", e)
            raise
        finally:
            session.close()


class ModelInferenceEventPostgresRepository(_BasePostgresRepository):
    """
    model_inference_event 테이블 repository.
    BUY/SELL 시에만 호출. HOLD 틱은 저장하지 않음 (시세 대량 저장 방지).
    """

    def create(self, dto: ModelInferenceEventCreate) -> int | None:
        session = self._session()
        try:
            m = ModelInferenceEventModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                model_version=dto.model_version,
                feature_set_version=dto.feature_set_version,
                input_snapshot=dto.input_snapshot,
                output_prediction=dto.output_prediction,
                paper_mode=dto.paper_mode,
                inference_at=dto.inference_at,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("ModelInferenceEvent create failed: %s", e)
            raise
        finally:
            session.close()

    def get_recent_scores(
        self,
        *,
        run_id: str,
        symbol: str | None = None,
        user_id: str = "default",
        limit: int = 500,
    ) -> list[float]:
        """Autopilot warmup — output_prediction.score 시간순(과거→최신)."""
        session = self._session()
        try:
            stmt = (
                select(ModelInferenceEventModel)
                .where(ModelInferenceEventModel.user_id == user_id)
                .where(ModelInferenceEventModel.run_id == run_id)
                .order_by(ModelInferenceEventModel.inference_at.desc())
                .limit(max(1, min(limit, 5000)))
            )
            if symbol:
                stmt = stmt.where(ModelInferenceEventModel.symbol == symbol)
            rows = session.execute(stmt).scalars().all()
            scores: list[float] = []
            for row in reversed(rows):
                pred = row.output_prediction or {}
                score = pred.get("score")
                if score is None:
                    continue
                scores.append(float(score))
            return scores
        finally:
            session.close()


class AuditLogPostgresRepository(_BasePostgresRepository):
    """audit_log 테이블 repository."""

    def create(self, dto: AuditLogCreate) -> int | None:
        session = self._session()
        try:
            m = AuditLogModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                correlation_id=dto.correlation_id or "",
                event=dto.event,
                data=dto.data,
                paper_mode=dto.paper_mode,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("AuditLog create failed: %s", e)
            raise
        finally:
            session.close()


class TradeResultPostgresRepository(_BasePostgresRepository):
    """trade_result 테이블 repository."""

    def exists(self, trade_id: str) -> bool:
        session = self._session()
        try:
            stmt = select(TradeResultModel.id).where(TradeResultModel.trade_id == trade_id)
            return session.execute(stmt).scalar_one_or_none() is not None
        finally:
            session.close()

    def create(self, dto: TradeResultCreate) -> int | None:
        if self.exists(dto.trade_id):
            return None
        session = self._session()
        try:
            m = TradeResultModel(
                trade_id=dto.trade_id,
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                side=dto.side,
                quantity=dto.quantity,
                entry_price=dto.entry_price,
                exit_price=dto.exit_price,
                entry_notional_usdt=dto.entry_notional_usdt,
                realized_pnl=dto.realized_pnl,
                pnl_pct=dto.pnl_pct,
                is_win=dto.is_win,
                exit_reason=dto.exit_reason,
                correlation_id=dto.correlation_id or "",
                opened_at=_ensure_kst(dto.opened_at),
                closed_at=_ensure_kst(dto.closed_at),
                hold_seconds=dto.hold_seconds,
                paper_mode=dto.paper_mode,
                position_snapshot_id=dto.position_snapshot_id,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("TradeResult create failed: %s", e)
            raise
        finally:
            session.close()

    def record_closed_trade(self, dto: TradeResultCreate) -> int | None:
        """trade_result insert + performance_daily upsert."""
        if self.exists(dto.trade_id):
            return None
        session = self._session()
        try:
            m = TradeResultModel(
                trade_id=dto.trade_id,
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                strategy_id=dto.strategy_id,
                symbol=dto.symbol,
                side=dto.side,
                quantity=dto.quantity,
                entry_price=dto.entry_price,
                exit_price=dto.exit_price,
                entry_notional_usdt=dto.entry_notional_usdt,
                realized_pnl=dto.realized_pnl,
                pnl_pct=dto.pnl_pct,
                is_win=dto.is_win,
                exit_reason=dto.exit_reason,
                correlation_id=dto.correlation_id or "",
                opened_at=_ensure_kst(dto.opened_at),
                closed_at=_ensure_kst(dto.closed_at),
                hold_seconds=dto.hold_seconds,
                paper_mode=dto.paper_mode,
                position_snapshot_id=dto.position_snapshot_id,
            )
            session.add(m)
            session.flush()

            closed_at = _ensure_kst(dto.closed_at)
            period_date = closed_at.date()
            is_win, is_loss, is_be = win_loss_flags(dto.realized_pnl)
            win_inc = 1 if is_win else 0
            loss_inc = 1 if is_loss else 0
            be_inc = 1 if is_be else 0
            gross_profit = dto.realized_pnl if is_win else 0.0
            gross_loss = abs(dto.realized_pnl) if is_loss else 0.0

            daily_table = PerformanceDailyModel.__table__
            stmt = insert(PerformanceDailyModel).values(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                period_date=period_date,
                trade_count=1,
                win_count=win_inc,
                loss_count=loss_inc,
                breakeven_count=be_inc,
                realized_pnl_sum=dto.realized_pnl,
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                avg_pnl_pct=dto.pnl_pct,
                paper_mode=dto.paper_mode,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_performance_daily_user_run_date",
                set_={
                    "trade_count": daily_table.c.trade_count + 1,
                    "win_count": daily_table.c.win_count + win_inc,
                    "loss_count": daily_table.c.loss_count + loss_inc,
                    "breakeven_count": daily_table.c.breakeven_count + be_inc,
                    "realized_pnl_sum": daily_table.c.realized_pnl_sum + dto.realized_pnl,
                    "gross_profit": daily_table.c.gross_profit + gross_profit,
                    "gross_loss": daily_table.c.gross_loss + gross_loss,
                    "avg_pnl_pct": (
                        daily_table.c.avg_pnl_pct * daily_table.c.trade_count + dto.pnl_pct
                    )
                    / (daily_table.c.trade_count + 1),
                    "updated_at": func.now(),
                },
            )
            session.execute(stmt)

            opening = session.execute(
                select(PerformanceDailyModel.opening_equity_usdt).where(
                    PerformanceDailyModel.user_id == (dto.user_id or "default"),
                    PerformanceDailyModel.run_id == dto.run_id,
                    PerformanceDailyModel.period_date == period_date,
                )
            ).scalar_one_or_none()
            if opening is not None:
                row = session.execute(
                    select(PerformanceDailyModel).where(
                        PerformanceDailyModel.user_id == (dto.user_id or "default"),
                        PerformanceDailyModel.run_id == dto.run_id,
                        PerformanceDailyModel.period_date == period_date,
                    )
                ).scalar_one()
                row.closing_equity_usdt = opening + row.realized_pnl_sum

            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("TradeResult record_closed_trade failed: %s", e)
            raise
        finally:
            session.close()

    def sum_realized_pnl(
        self, *, user_id: str, run_id: str | None = None
    ) -> float:
        session = self._session()
        try:
            stmt = select(func.coalesce(func.sum(TradeResultModel.realized_pnl), 0.0)).where(
                TradeResultModel.user_id == user_id
            )
            if run_id:
                stmt = stmt.where(TradeResultModel.run_id == run_id)
            return float(session.execute(stmt).scalar_one())
        finally:
            session.close()


class PerformanceDailyPostgresRepository(_BasePostgresRepository):
    """performance_daily 테이블 repository."""

    def set_opening_equity_if_missing(
        self,
        *,
        user_id: str,
        run_id: str,
        period_date,
        equity_usdt: float,
        paper_mode: bool,
    ) -> None:
        session = self._session()
        try:
            row = session.execute(
                select(PerformanceDailyModel).where(
                    PerformanceDailyModel.user_id == user_id,
                    PerformanceDailyModel.run_id == run_id,
                    PerformanceDailyModel.period_date == period_date,
                )
            ).scalar_one_or_none()
            if row is not None:
                if row.opening_equity_usdt is None:
                    row.opening_equity_usdt = equity_usdt
                    row.closing_equity_usdt = equity_usdt + row.realized_pnl_sum
            else:
                session.add(
                    PerformanceDailyModel(
                        user_id=user_id,
                        run_id=run_id,
                        period_date=period_date,
                        opening_equity_usdt=equity_usdt,
                        closing_equity_usdt=equity_usdt,
                        paper_mode=paper_mode,
                    )
                )
            session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("PerformanceDaily set_opening_equity failed: %s", e)
            raise
        finally:
            session.close()


class EquitySnapshotPostgresRepository(_BasePostgresRepository):
    """equity_snapshot 테이블 repository."""

    def create(self, dto: EquitySnapshotCreate) -> int | None:
        session = self._session()
        try:
            m = EquitySnapshotModel(
                user_id=dto.user_id or "default",
                run_id=dto.run_id,
                snapshot_at=_ensure_kst(dto.snapshot_at),
                snapshot_date=dto.snapshot_date,
                equity_usdt=dto.equity_usdt,
                cumulative_realized_pnl=dto.cumulative_realized_pnl,
                source=dto.source,
                paper_mode=dto.paper_mode,
            )
            session.add(m)
            session.commit()
            session.refresh(m)
            return m.id
        except Exception as e:
            session.rollback()
            logger.exception("EquitySnapshot create failed: %s", e)
            raise
        finally:
            session.close()

    def get_reference_equity(
        self,
        *,
        user_id: str,
        run_id: str,
        before_date=None,
    ) -> float | None:
        session = self._session()
        try:
            stmt = (
                select(EquitySnapshotModel.equity_usdt)
                .where(
                    EquitySnapshotModel.user_id == user_id,
                    EquitySnapshotModel.run_id == run_id,
                )
                .order_by(EquitySnapshotModel.snapshot_at.asc())
            )
            if before_date is not None:
                stmt = stmt.where(EquitySnapshotModel.snapshot_date <= before_date)
            val = session.execute(stmt.limit(1)).scalar_one_or_none()
            return float(val) if val is not None else None
        finally:
            session.close()


class PostgresRepositoryFactory:
    """Postgres repository 팩토리."""

    def __init__(self) -> None:
        self._ohlcv_candle = OhlcvCandlePostgresRepository()
        self._engine_run = EngineRunPostgresRepository()
        self._strategy_config = StrategyConfigSnapshotPostgresRepository()
        self._signal_event = SignalEventPostgresRepository()
        self._order_request = OrderRequestPostgresRepository()
        self._order_execution = OrderExecutionPostgresRepository()
        self._position_snapshot = PositionSnapshotPostgresRepository()
        self._risk_event = RiskEventPostgresRepository()
        self._model_inference = ModelInferenceEventPostgresRepository()
        self._audit_log = AuditLogPostgresRepository()
        self._trade_result = TradeResultPostgresRepository()
        self._performance_daily = PerformanceDailyPostgresRepository()
        self._equity_snapshot = EquitySnapshotPostgresRepository()

    @property
    def ohlcv_candle(self) -> OhlcvCandlePostgresRepository:
        return self._ohlcv_candle

    @property
    def engine_run(self) -> EngineRunPostgresRepository:
        return self._engine_run

    @property
    def strategy_config_snapshot(self) -> StrategyConfigSnapshotPostgresRepository:
        return self._strategy_config

    @property
    def signal_event(self) -> SignalEventPostgresRepository:
        return self._signal_event

    @property
    def order_request(self) -> OrderRequestPostgresRepository:
        return self._order_request

    @property
    def order_execution(self) -> OrderExecutionPostgresRepository:
        return self._order_execution

    @property
    def position_snapshot(self) -> PositionSnapshotPostgresRepository:
        return self._position_snapshot

    @property
    def risk_event(self) -> RiskEventPostgresRepository:
        return self._risk_event

    @property
    def model_inference_event(self) -> ModelInferenceEventPostgresRepository:
        return self._model_inference

    @property
    def audit_log(self) -> AuditLogPostgresRepository:
        return self._audit_log

    @property
    def trade_result(self) -> TradeResultPostgresRepository:
        return self._trade_result

    @property
    def performance_daily(self) -> PerformanceDailyPostgresRepository:
        return self._performance_daily

    @property
    def equity_snapshot(self) -> EquitySnapshotPostgresRepository:
        return self._equity_snapshot
