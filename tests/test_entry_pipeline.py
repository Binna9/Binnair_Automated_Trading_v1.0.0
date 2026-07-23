"""soft entry / hard risk 경계 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from binnair_trading_engine.domain.models import (
    EngineContext,
    MarketSnapshot,
    OrderIntent,
    OrderSide,
    OrderType,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.engine.entry_pipeline import (
    approve_entry_risk,
    evaluate_soft_entry_signal,
)
from binnair_trading_engine.risk.checker import RiskCheckResult
from binnair_trading_engine.signal.policy import ConsecutiveSignalPolicy


def _snap() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XRPUSDT",
        price=1.1,
        timestamp=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        correlation_id="corr-1",
    )


def _ctx() -> EngineContext:
    return EngineContext(
        version="1.0.0",
        run_id="prod_timesfm_run",
        strategy_id="s",
        model_version="timesfm-2.5-200m",
        feature_set_version="price-history-v1",
    )


def test_soft_entry_policy_filtered_until_consecutive():
    pred = Prediction(
        action=SignalAction.BUY,
        confidence=1.0,
        score=0.01,
        price_hint=1.1,
    )
    predictor = MagicMock()
    predictor.predict.return_value = pred
    policy = ConsecutiveSignalPolicy(consecutive_required=2, mode="long_short")
    snap = _snap()
    trade_ctx = TradeContext.from_snapshot(snap, _ctx())

    first = evaluate_soft_entry_signal(
        predictor=predictor,
        signal_policy=policy,
        snapshot=snap,
        trade_ctx=trade_ctx,
        engine_ctx=_ctx(),
    )
    assert first.status == "policy_filtered"

    second = evaluate_soft_entry_signal(
        predictor=predictor,
        signal_policy=policy,
        snapshot=snap,
        trade_ctx=trade_ctx,
        engine_ctx=_ctx(),
    )
    assert second.status == "candidate"
    assert second.signal is not None
    assert second.signal.action == SignalAction.BUY


def test_soft_entry_awaiting_candle():
    pred = Prediction(
        action=SignalAction.HOLD,
        confidence=0.0,
        hold_reason="awaiting_candle_close",
    )
    predictor = MagicMock()
    predictor.predict.return_value = pred
    policy = ConsecutiveSignalPolicy(consecutive_required=1, mode="long_short")
    snap = _snap()
    out = evaluate_soft_entry_signal(
        predictor=predictor,
        signal_policy=policy,
        snapshot=snap,
        trade_ctx=TradeContext.from_snapshot(snap, _ctx()),
        engine_ctx=_ctx(),
    )
    assert out.status == "awaiting_candle"


def test_approve_entry_risk_delegates():
    risk = MagicMock()
    risk.check.return_value = RiskCheckResult(passed=False, reason="daily_loss_limit")
    intent = OrderIntent(
        symbol="XRPUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10.0,
        price=1.1,
    )
    snap = _snap()
    trade_ctx = TradeContext.from_snapshot(snap, _ctx())
    result = approve_entry_risk(
        risk,
        intent=intent,
        trade_ctx=trade_ctx,
        current_positions=[],
        recent_orders=[],
        daily_pnl=-999.0,
    )
    assert result.passed is False
    assert result.reason == "daily_loss_limit"
    risk.check.assert_called_once()
