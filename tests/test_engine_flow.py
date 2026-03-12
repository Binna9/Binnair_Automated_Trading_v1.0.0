"""최소 엔진 흐름 테스트: market tick -> signal -> risk -> order -> execution."""

from datetime import datetime, timezone
import uuid

import pytest

from binnair_trading_engine.app.bootstrap import bootstrap
from binnair_trading_engine.domain.models import MarketSnapshot, SignalAction
from binnair_trading_engine.predictor import DummyPredictor


def test_process_tick_buy_flow() -> None:
    """BUY 시그널 -> 주문 실행 -> storage에 order/trade 반영."""
    engine = bootstrap()
    engine._predictor = DummyPredictor(force_action=SignalAction.BUY)

    engine.start()

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        price=50000.0,
        timestamp=datetime.now(timezone.utc),
        run_id=engine._ctx.run_id,
        correlation_id=str(uuid.uuid4()),
    )
    engine.process_tick(snapshot)

    # Paper exchange에 포지션 생김
    positions = engine._exchange.get_all_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert positions[0].quantity > 0

    # Storage에 order 저장됨
    orders = engine._storage.get_recent_orders(
        engine._ctx.run_id, "BTCUSDT", limit=5
    )
    assert len(orders) >= 1
    assert orders[0].side.value == "BUY"

    engine.stop()


def test_process_tick_hold_no_order() -> None:
    """HOLD 시그널 -> 주문 없음."""
    engine = bootstrap()
    # DummyPredictor 기본값 HOLD
    engine.start()

    snapshot = MarketSnapshot(
        symbol="ETHUSDT",
        price=3000.0,
        timestamp=datetime.now(timezone.utc),
        run_id=engine._ctx.run_id,
    )
    engine.process_tick(snapshot)

    positions = engine._exchange.get_all_positions()
    assert len(positions) == 0

    engine.stop()
