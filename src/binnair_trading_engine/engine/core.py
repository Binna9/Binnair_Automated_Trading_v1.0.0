"""
자동매매 한 사이클의 오케스트레이션을 담당한다.
시세 입력부터 예측, 시그널 정책, 전략, 리스크, 주문, 포지션 저장까지 연결한다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from binnair_trading_engine.config import EngineConfig
from binnair_trading_engine.domain.models import (
    EngineContext,
    MarketSnapshot,
    OrderIntent,
    OrderSide,
    OrderType,
    Position,
    Prediction,
    Signal,
    SignalAction,
    Trade,
    TradeContext,
)
from binnair_trading_engine.exchange import ExchangeAdapter
from binnair_trading_engine.position import PositionManager
from binnair_trading_engine.predictor import Predictor
from binnair_trading_engine.risk import RiskChecker, RiskCheckResult
from binnair_trading_engine.signal import ConsecutiveSignalPolicy
from binnair_trading_engine.state import StateManager
from binnair_trading_engine.storage import StorageLayer
from binnair_trading_engine.strategy import Strategy
from binnair_trading_engine.strategy.exit_manager import ExitManager

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
        position_manager: PositionManager,
        exit_manager: ExitManager,
        signal_policy: ConsecutiveSignalPolicy,
    ) -> None:
        self._config = config
        self._ctx = ctx
        self._exchange = exchange
        self._predictor = predictor
        self._risk = risk_checker
        self._strategy = strategy
        self._storage = storage
        self._state = state_manager
        self._position_manager = position_manager
        self._exit_manager = exit_manager
        self._signal_policy = signal_policy
        self._shutdown_done = False

    def start(self) -> None:
        """엔진 시작: DB 포지션 복구, 상태 복구, engine_run 기록."""
        self._state.start(self._ctx)
        self._recover_positions_from_db()
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

    def _recover_positions_from_db(self) -> None:
        """
        trade.position_snapshot에서 심볼별 최신 OPEN 포지션 복구.
        run_id 무관, DB가 기준 상태. 재기동 시 포지션 유실 방지.
        """
        if not hasattr(self._storage, "get_latest_open_position_snapshots"):
            return
        symbol = self._config.market_data.symbol
        snapshots = self._storage.get_latest_open_position_snapshots([symbol])
        for s in snapshots:
            pos = self._position_manager.restore_from_snapshot(s)
            if pos:
                logger.info(
                    "Position recovered from DB",
                    extra={
                        "run_id": self._ctx.run_id,
                        "symbol": pos.symbol,
                        "entry": pos.avg_entry_price,
                        "tp": pos.tp_price,
                        "sl": pos.sl_price,
                    },
                )

    def stop(self) -> None:
        """엔진 종료: 열린 포지션 청산(설정 시), engine_run status 업데이트."""
        if self._shutdown_done:
            return
        self._shutdown_done = True

        if self._config.flatten_on_shutdown:
            try:
                self._flatten_open_positions_on_shutdown()
            except Exception:
                logger.exception(
                    "Failed to flatten positions on shutdown",
                    extra={"run_id": self._ctx.run_id},
                )

        self._storage.record_engine_stop(self._ctx.run_id, "stopped")
        self._state.stop()
        logger.info("Engine stopped", extra={"run_id": self._ctx.run_id})

    def _flatten_open_positions_on_shutdown(self) -> None:
        """graceful 종료 시 엔진이 관리 중인 OPEN 포지션을 시장가로 청산한다."""
        run_id = self._ctx.run_id
        corr_id = str(uuid.uuid4())
        open_positions = self._position_manager.list_open_positions()
        if not open_positions:
            return

        logger.info(
            "Flattening open positions on shutdown",
            extra={
                "run_id": run_id,
                "count": len(open_positions),
                "correlation_id": corr_id,
            },
        )

        for pos in open_positions:
            price = self._resolve_shutdown_exit_price(pos.symbol, pos)
            snapshot = MarketSnapshot(
                symbol=pos.symbol,
                price=price,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=corr_id,
            )
            side = OrderSide.SELL if pos.is_long() else OrderSide.BUY
            intent = OrderIntent(
                symbol=pos.symbol,
                side=side,
                order_type=OrderType.MARKET,
                quantity=pos.quantity,
                price=None,
                reduce_only=True,
                position_side=pos.side,
            )
            self._submit_exit_order(
                snapshot=snapshot,
                pos=pos,
                intent=intent,
                exit_reason="SHUTDOWN",
                run_id=run_id,
                corr_id=corr_id,
            )

    def _resolve_shutdown_exit_price(self, symbol: str, pos: Position) -> float:
        """종료 시 체결가 추정. ticker 조회 실패 시 거래소/포지션 진입가로 대체."""
        from binnair_trading_engine.market_data.binance_rest import BinanceRestMarketData

        md = self._config.market_data
        provider = BinanceRestMarketData(base_url=md.base_url, timeout=md.timeout)
        snap = provider.fetch_snapshot(symbol, run_id=self._ctx.run_id)
        if snap is not None and snap.price > 0:
            return snap.price

        exch_pos = self._exchange.get_position(symbol)
        if exch_pos is not None and exch_pos.avg_entry_price > 0:
            return exch_pos.avg_entry_price

        return pos.avg_entry_price

    def process_tick(self, snapshot: MarketSnapshot) -> None:
        """
        단일 마켓 틱 처리.
        포지션 우선 분기: 보유 중이면 exit(TP/SL) 관리, 없으면 predictor 진입 흐름.
        """
        run_id = self._ctx.run_id
        corr_id = snapshot.correlation_id or str(uuid.uuid4())
        symbol = snapshot.symbol

        # 1. 포지션 우선 분기: 보유 중이면 predictor skip, exit 로직으로
        pos = self._position_manager.get_position(symbol)
        if pos is not None and pos.is_open():
            self._process_exit_tick(snapshot, pos, run_id, corr_id)
            return

        # 2. 포지션 없음 → 기존 predictor → signal → strategy → risk → exchange 흐름
        trade_ctx = TradeContext.from_snapshot(snapshot, self._ctx)
        pred = self._predictor.predict(snapshot, trade_ctx)

        # Phase 1: Predictor.predict() 직후 model_inference_event 항상 저장
        if pred is not None:
            self._storage.save_model_inference(snapshot, pred)

        if pred is None:
            logger.debug(
                "No prediction",
                extra={"run_id": run_id, "symbol": symbol, "correlation_id": corr_id},
            )
            return

        self._signal_policy.record(symbol, pred.action)

        if pred.action != SignalAction.BUY or not self._signal_policy.allows_entry(symbol):
            logger.debug(
                "Signal filtered by policy",
                extra={
                    "run_id": run_id,
                    "symbol": symbol,
                    "action": pred.action.value,
                    "correlation_id": corr_id,
                },
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

        # Phase 1: HOLD 아니면 signal_event 저장 (신호 생성 시점)
        self._storage.save_signal(signal)

        # 3. order creation (strategy)
        intent = self._strategy.decide(signal, pred, trade_ctx)
        if intent is None:
            return

        # 3b. 추가 진입 금지: 이미 포지션 있으면 신규 진입 생성 안 함
        if self._position_manager.has_open_position(symbol):
            logger.debug(
                "Skip entry: already has open position",
                extra={"run_id": run_id, "symbol": symbol, "correlation_id": corr_id},
            )
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

        # 7. persistence (signal은 이미 신호 생성 시점에 저장됨)
        self._storage.save_order(order)

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

            # 진입 체결 시 PositionManager에 포지션 생성 + position_snapshot 저장
            if order.side in (OrderSide.BUY, OrderSide.SELL) and order.price is not None:
                if not self._position_manager.has_open_position(symbol):
                    executed_price = order.price
                    side = "LONG" if order.side == OrderSide.BUY else "SHORT"
                    tp_price = intent.take_profit_price
                    sl_price = intent.stop_loss_price
                    pos = self._position_manager.open_position(
                        symbol=symbol,
                        side=side,
                        quantity=order.quantity,
                        entry_price=executed_price,
                        tp_price=tp_price,
                        sl_price=sl_price,
                    )
                    self._storage.save_position(pos)
                    self._signal_policy.reset(symbol)
                    logger.info(
                        "Position opened with TP/SL",
                        extra={
                            "run_id": run_id,
                            "symbol": symbol,
                            "entry": executed_price,
                            "tp": tp_price,
                            "sl": sl_price,
                            "correlation_id": corr_id,
                        },
                    )
                    if self._config.exchange.oco_enabled:
                        exit_orders = self._exchange.place_exit_orders(
                            symbol=symbol,
                            position_side=side,
                            quantity=order.quantity,
                            take_profit_price=tp_price,
                            stop_loss_price=sl_price,
                        )
                        for eo in exit_orders:
                            eo.run_id = run_id
                            eo.correlation_id = corr_id
                            self._storage.save_order(eo)
                else:
                    logger.warning(
                        "Skip position creation: already has open position (unexpected)",
                        extra={"run_id": run_id, "symbol": symbol},
                    )
            elif order.side in (OrderSide.BUY, OrderSide.SELL) and order.price is None:
                logger.warning(
                    "Skip position creation: executed_price is None (no fallback)",
                    extra={"run_id": run_id, "symbol": symbol},
                )

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

    def _process_exit_tick(
        self,
        snapshot: MarketSnapshot,
        pos: Position,
        run_id: str,
        corr_id: str,
    ) -> None:
        """
        보유 포지션 exit 관리.
        1. TP/SL 도달 시 우선 청산
        2. TP/SL 미도달 시 모델 SELL 3회 연속이면 롱 청산
        """
        result = self._exit_manager.check_exit(pos, snapshot)
        if result is not None:
            if self._exchange.manages_exit_orders:
                # 거래소 보호주문이 청산을 처리하므로 로컬 TP/SL 청산 주문은 제출하지 않는다.
                return
            self._submit_exit_order(
                snapshot=snapshot,
                pos=pos,
                intent=result.intent,
                exit_reason=result.reason,
                run_id=run_id,
                corr_id=corr_id,
            )
            return

        trade_ctx = TradeContext.from_snapshot(snapshot, self._ctx)
        pred = self._predictor.predict(snapshot, trade_ctx)
        if pred is not None:
            self._storage.save_model_inference(snapshot, pred)
        if pred is None:
            return

        self._signal_policy.record(snapshot.symbol, pred.action)
        if not pos.is_long() or not self._signal_policy.allows_long_exit(snapshot.symbol):
            return

        intent = OrderIntent(
            symbol=snapshot.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
            price=None,
            reduce_only=True,
            position_side="LONG",
        )
        self._submit_exit_order(
            snapshot=snapshot,
            pos=pos,
            intent=intent,
            exit_reason="MODEL_SELL",
            run_id=run_id,
            corr_id=corr_id,
        )

    def _submit_exit_order(
        self,
        snapshot: MarketSnapshot,
        pos: Position,
        intent: OrderIntent,
        exit_reason: str,
        run_id: str,
        corr_id: str,
    ) -> None:
        """청산 주문 실행 및 position_snapshot/audit 저장."""
        symbol = snapshot.symbol
        price = snapshot.price
        execution_price = price
        order = self._exchange.submit_order(intent, execution_price=execution_price)
        if not order:
            return

        order.run_id = run_id
        order.correlation_id = corr_id
        self._state.update_position(intent, order)
        self._storage.save_order(order)

        if order.status.value == "FILLED":
            trade = Trade(
                trade_id=str(uuid.uuid4()),
                order_id=order.order_id or "",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price or price,
                run_id=run_id,
                correlation_id=corr_id,
            )
            self._storage.save_trade(trade)

            exit_price_val = order.price or price
            closed_pos = self._position_manager.close_position(
                symbol, exit_price=exit_price_val, exit_reason=exit_reason
            )
            if closed_pos:
                self._storage.save_position(closed_pos)
                self._signal_policy.reset(symbol)
                exit_ctx = TradeContext.from_snapshot(snapshot, self._ctx)
                exit_ctx.correlation_id = corr_id  # type: ignore[attr-defined]
                self._storage.save_audit(
                    "position_closed",
                    intent,
                    exit_ctx,
                    reason=exit_reason,
                    extra_data={
                        "exit_reason": exit_reason,
                        "realized_pnl": closed_pos.realized_pnl,
                    },
                )

            logger.info(
                f"Position closed ({exit_reason})",
                extra={
                    "run_id": run_id,
                    "symbol": symbol,
                    "reason": exit_reason,
                    "exit_price": order.price or price,
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
