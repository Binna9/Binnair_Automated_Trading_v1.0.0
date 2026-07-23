"""
진입 결정 경계 — soft signal vs hard risk.

Risk-first 원칙:
- Predictor + consecutive policy = 약한 후보(soft)
- RiskChecker = 강한 최종 거부권(hard)
- 엔진은 오케스트레이션만 하고, 숫자 튜닝은 이 모듈이 아닌 config/Phase2에서.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from binnair_trading_engine.domain.models import (
    EngineContext,
    MarketSnapshot,
    Order,
    OrderIntent,
    Position,
    Prediction,
    Signal,
    TradeContext,
)
from binnair_trading_engine.predictor.interface import Predictor
from binnair_trading_engine.risk.checker import RiskChecker, RiskCheckResult
from binnair_trading_engine.signal.policy import ConsecutiveSignalPolicy

SoftEntryStatus = Literal[
    "awaiting_candle",
    "no_prediction",
    "policy_filtered",
    "candidate",
]


@dataclass(frozen=True)
class SoftEntryEval:
    """예측·정책 단계 결과. candidate 만 주문 의도 생성 대상."""

    status: SoftEntryStatus
    prediction: Prediction | None = None
    signal: Signal | None = None
    detail: str = ""


def evaluate_soft_entry_signal(
    *,
    predictor: Predictor,
    signal_policy: ConsecutiveSignalPolicy,
    snapshot: MarketSnapshot,
    trade_ctx: TradeContext,
    engine_ctx: EngineContext,
) -> SoftEntryEval:
    """
    Soft gate: TimesFM(등) 예측 + consecutive policy.

    최종 진입 권한이 아님. candidate 여도 hard risk 를 통과해야 한다.
    """
    pred = predictor.predict(snapshot, trade_ctx, for_exit=False)

    if pred is not None and pred.hold_reason == "awaiting_candle_close":
        return SoftEntryEval(
            status="awaiting_candle",
            prediction=pred,
            detail="awaiting_candle_close",
        )

    if pred is None:
        return SoftEntryEval(status="no_prediction", detail="no_prediction")

    signal_policy.record(snapshot.symbol, pred.action)
    if not signal_policy.allows_entry_action(snapshot.symbol, pred.action):
        return SoftEntryEval(
            status="policy_filtered",
            prediction=pred,
            detail=(
                f"policy_filtered action={pred.action.value} "
                f"mode={signal_policy.mode} "
                f"consecutive={signal_policy.consecutive_required}"
            ),
        )

    signal = Signal(
        symbol=snapshot.symbol,
        action=pred.action,
        confidence=pred.confidence,
        price_hint=pred.price_hint or snapshot.price,
        timestamp=snapshot.timestamp,
        run_id=engine_ctx.run_id,
        strategy_id=engine_ctx.strategy_id,
        model_version=engine_ctx.model_version,
        feature_set_version=engine_ctx.feature_set_version,
    )
    return SoftEntryEval(
        status="candidate",
        prediction=pred,
        signal=signal,
        detail="soft_candidate",
    )


def approve_entry_risk(
    risk: RiskChecker,
    *,
    intent: OrderIntent,
    trade_ctx: TradeContext,
    current_positions: list[Position],
    recent_orders: list[Order],
    daily_pnl: float,
) -> RiskCheckResult:
    """Hard gate: 일손실·연속손절·명목·중복 등. 통과해야만 실행."""
    return risk.check(
        intent,
        trade_ctx,
        current_positions,
        recent_orders,
        daily_pnl,
    )
