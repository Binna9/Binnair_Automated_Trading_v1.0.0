"""
자동매매 엔진 코어.
market snapshot -> signal evaluation -> risk check -> order -> execution -> position/audit
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from binnair_trading_engine.config import EngineConfig
from binnair_trading_engine.domain.models import (
    EngineContext,
    MarketSnapshot,
    OrderIntent,
    OrderSide,
    OrderType,
    Prediction,
    Signal,
    SignalAction,
    Trade,
    TradeContext,
)
from binnair_trading_engine.exchange import ExchangeAdapter
from binnair_trading_engine.predictor import Predictor
from binnair_trading_engine.risk import RiskChecker, RiskCheckResult
from binnair_trading_engine.state import StateManager
from binnair_trading_engine.storage import StorageLayer
from binnair_trading_engine.strategy import Strategy

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    자동매매 실행 엔진.
    market snapshot -> signal evaluation -> risk check -> order creation -> execution -> position update -> persistence
    """

    def __init__(
        self,
        config: EngineConfig,
        ctx: EngineContext,
        exchange: ExchangeAdapter,
        predictor: Predictor,
        risk_checker: RiskChecker,
        strategy: Strategy,
        storage: StorageLayer,
        state_manager: StateManager,
    ) -> None:
        self._config = config
        self._ctx = ctx
        self._exchange = exchange
        self._predictor = predictor
        self._risk = risk_checker
        self._strategy = strategy
        self._storage = storage
        self._state = state_manager

    def start(self) -> None:
        """엔진 시작: 상태 복구, engine_run 기록."""
        self._state.start(self._ctx)
        self._storage.record_engine_start(
            ctx=self._ctx,
            paper_mode=self._config.exchange.paper_mode,
        )
        logger.info(
            "Engine started",
            extra={
                "run_id": self._ctx.run_id,
                "strategy_id": self._ctx.strategy_id,
            },
        )

    def stop(self) -> None:
        """엔진 종료: engine_run status 업데이트."""
        self._storage.record_engine_stop(self._ctx.run_id, "stopped")
        self._state.stop()
        logger.info("Engine stopped", extra={"run_id": self._ctx.run_id})

    def process_tick(self, snapshot: MarketSnapshot) -> None:
        """
        단일 마켓 틱 처리.
        1. market snapshot 수신
        2. signal evaluation (predictor)
        3. risk check
        4. order creation
        5. execution
        6. position update
        7. persistence/audit logging
        """
        run_id = self._ctx.run_id
        corr_id = snapshot.correlation_id or str(uuid.uuid4())
        symbol = snapshot.symbol

        trade_ctx = TradeContext.from_snapshot(snapshot, self._ctx)

        # 2. signal evaluation
        pred = self._predictor.predict(snapshot, trade_ctx)
        if pred is None or pred.action == SignalAction.HOLD:
            logger.debug(
                "Signal HOLD or no prediction",
                extra={"run_id": run_id, "symbol": symbol, "correlation_id": corr_id},
            )
            return

        signal = Signal(
            symbol=symbol,
            action=pred.action,
            confidence=pred.confidence,
            price_hint=pred.price_hint or snapshot.price,
            timestamp=snapshot.timestamp,
            run_id=run_id,
            strategy_id=self._ctx.strategy_id,
            model_version=self._ctx.model_version,
            feature_set_version=self._ctx.feature_set_version,
        )

        # 3. order creation (strategy)
        intent = self._strategy.decide(signal, pred, trade_ctx)
        if intent is None:
            return

        # 4. risk check
        positions = list(self._exchange.get_all_positions())
        recent_orders = self._storage.get_recent_orders(run_id, symbol, limit=50)
        daily_pnl = self._storage.get_daily_pnl(run_id)

        risk_result = self._risk.check(
            intent, trade_ctx, positions, recent_orders, daily_pnl
        )
        if not risk_result.passed:
            self._storage.save_audit(
                "risk_rejected", intent, trade_ctx, reason=risk_result.reason
            )
            logger.warning(
                "Risk check rejected",
                extra={
                    "run_id": run_id,
                    "symbol": symbol,
                    "reason": risk_result.reason,
                    "correlation_id": corr_id,
                },
            )
            return

        # 5. execution (paper exchange)
        execution_price = intent.price or snapshot.price
        order = self._exchange.submit_order(intent, execution_price=execution_price)
        if not order:
            return

        order.run_id = run_id
        order.correlation_id = corr_id

        # 6. position update
        self._state.update_position(intent, order)

        # 7. persistence (BUY/SELL 시에만 도달. HOLD는 early return)
        self._storage.save_signal(signal)
        self._storage.save_order(order)
        if self._config.persist_model_inference:
            self._storage.save_model_inference(snapshot, pred)

        if order.status.value == "FILLED":
            trade = Trade(
                trade_id=str(uuid.uuid4()),
                order_id=order.order_id or "",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price or snapshot.price,
                run_id=run_id,
                correlation_id=corr_id,
            )
            self._storage.save_trade(trade)

        logger.info(
            "Order executed",
            extra={
                "run_id": run_id,
                "order_id": order.order_id,
                "symbol": symbol,
                "side": intent.side.value,
                "correlation_id": corr_id,
            },
        )

    def run_cycle(self, snapshot: MarketSnapshot | None = None) -> None:
        """
        한 사이클 실행. snapshot 없으면 heartbeat만.
        """
        self._state.heartbeat()
        if snapshot:
            self.process_tick(snapshot)
