#!/usr/bin/env python3
"""
MVP 검증: 진입/보유/TP/SL 청산 시나리오.

시나리오:
1. 포지션 없음 + BUY → 진입, 포지션 생성, TP/SL 저장
2. 포지션 보유 + 가격 TP/SL 범위 안 → 주문 없음, 포지션 유지
3. 포지션 보유 + TP 도달 → SELL 청산, 포지션 CLOSED
4. 포지션 보유 + SL 도달 → SELL 청산, 포지션 CLOSED
5. 포지션 보유 + predictor SELL → 무시 (청산 안 함)

실행: CONFIG_PATH=config/config.yaml python scripts/verify_mvp.py
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.app.bootstrap import bootstrap
from binnair_trading_engine.domain.models import EngineContext, MarketSnapshot, SignalAction
from binnair_trading_engine.infra.persistence.session import (
    get_engine,
    get_storage_schema,
)
from binnair_trading_engine.predictor import DummyPredictor

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logging.getLogger("binnair_trading_engine").setLevel(logging.INFO)

SYMBOL = "BTCUSDT"
ENTRY_PRICE = 50000.0
# tp_pct=0.02 → TP=51000, sl_pct=0.01 → SL=49500
TP_PRICE = 51000.0  # entry * 1.02
SL_PRICE = 49500.0  # entry * 0.99
PRICE_IN_RANGE = 50500.0  # 49500 < 50500 < 51000


def _snap(price: float, run_id: str) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=SYMBOL,
        price=price,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        correlation_id=str(uuid.uuid4()),
    )


def _order_count(engine) -> int:
    return len(engine._exchange._orders)


def run_scenario(name: str, engine, predictor_action: SignalAction, price: float) -> None:
    engine._predictor = DummyPredictor(force_action=predictor_action)
    engine.run_cycle(_snap(price, engine._ctx.run_id))


def _clear_open_positions_for_verify(symbol: str) -> None:
    """검증 전 해당 심볼 OPEN position_snapshot 삭제. 복구 시 빈 상태에서 시작."""
    schema = get_storage_schema()
    eng = get_engine()
    with eng.connect() as conn:
        conn.execute(
            text(f'DELETE FROM "{schema}".position_snapshot WHERE symbol = :symbol AND status = \'OPEN\''),
            {"symbol": symbol},
        )
        conn.commit()


def _verify_db_state(run_id: str, fail) -> None:
    """DB에 signal_event, order_request, order_execution, position_snapshot이 DDL대로 저장됐는지 검증."""
    schema = get_storage_schema()
    eng = get_engine()

    queries = [
        (
            "signal_event",
            f'select id, run_id, symbol, signal_action, confidence, event_at from "{schema}".signal_event where run_id = :run_id order by id',
        ),
        (
            "order_request",
            f'select id, run_id, symbol, order_id, side, order_type, quantity, requested_at from "{schema}".order_request where run_id = :run_id order by id',
        ),
        (
            "order_execution",
            f'select id, order_request_id, run_id, symbol, order_id, status, executed_price, executed_quantity, executed_at from "{schema}".order_execution where run_id = :run_id order by id',
        ),
        (
            "position_snapshot",
            f'select id, run_id, symbol, side, quantity, avg_entry_price, tp_price, sl_price, status, exit_reason, exit_price, realized_pnl, snapshot_at from "{schema}".position_snapshot where run_id = :run_id order by id',
        ),
    ]

    with eng.connect() as conn:
        for name, q in queries:
            result = conn.execute(text(q), {"run_id": run_id})
            rows = result.fetchall()
            cols = result.keys()
            print(f"\n  [{name}] run_id={run_id} ({len(rows)} rows)")
            if rows:
                # 헤더
                print("    " + " | ".join(str(c) for c in cols))
                for r in rows:
                    print("    " + " | ".join(str(v) for v in r))
            else:
                print("    (empty)")

        # position_snapshot: OPEN → CLOSED 흐름 + 청산 정보 확인
        ps_result = conn.execute(
            text(
                f'select id, status, quantity, avg_entry_price, tp_price, sl_price, exit_reason, exit_price, realized_pnl, snapshot_at from "{schema}".position_snapshot where run_id = :run_id order by id'
            ),
            {"run_id": run_id},
        )
        ps_rows = ps_result.fetchall()
        statuses = [r[1] for r in ps_rows]
        if "OPEN" not in statuses:
            fail("position_snapshot에 OPEN 상태가 있어야 함")
        if "CLOSED" not in statuses:
            fail("position_snapshot에 CLOSED 상태가 있어야 함 (TP/SL 청산 기록)")
        # CLOSED row에서 exit_reason, exit_price, realized_pnl 검증
        for r in ps_rows:
            if r[1] == "CLOSED":
                exit_reason, exit_price, realized_pnl = r[6], r[7], r[8]
                if not exit_reason or exit_reason not in ("TAKE_PROFIT", "STOP_LOSS"):
                    fail(f"CLOSED row에 exit_reason(TAKE_PROFIT|STOP_LOSS) 필요: {exit_reason}")
                if exit_price is None:
                    fail("CLOSED row에 exit_price 필요")
                if realized_pnl is None:
                    fail("CLOSED row에 realized_pnl 필요")
                break
    print("  OK: DB 레벨 검증 (signal_event, order_request, order_execution, position_snapshot OPEN→CLOSED + exit_reason/exit_price/realized_pnl)", flush=True)


def main() -> int:
    config_path = os.environ.get("CONFIG_PATH") or str(
        Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    )
    if not Path(config_path).exists():
        print("CONFIG_PATH 또는 config/config.yaml 필요. storage.backend=postgres.")
        return 1

    os.environ["CONFIG_PATH"] = config_path
    engine = bootstrap(Path(config_path))

    if getattr(engine._config.storage, "backend", "memory") != "postgres":
        print("storage.backend=postgres 필요.")
        return 1

    # 실행마다 고유 run_id 사용 → 이전 실행 주문이 get_recent_orders로 반환되어 중복 거부 방지
    verify_run_id = f"verify_{uuid.uuid4().hex[:8]}"
    engine._ctx = EngineContext(
        version=engine._ctx.version,
        run_id=verify_run_id,
        strategy_id=engine._ctx.strategy_id,
        model_version=engine._ctx.model_version,
        feature_set_version=engine._ctx.feature_set_version,
    )
    engine._position_manager._run_id = verify_run_id

    _clear_open_positions_for_verify(SYMBOL)
    engine.start()
    run_id = engine._ctx.run_id
    pm = engine._position_manager

    def ok(msg: str) -> None:
        print(f"  OK: {msg}", flush=True)

    def fail(msg: str) -> None:
        print(f"  FAIL: {msg}", flush=True)
        raise AssertionError(msg)

    try:
        # === 시나리오 1: 포지션 없음 + BUY → 진입, 포지션+TP/SL ===
        print("\n[시나리오 1] 포지션 없음 + BUY → 진입, 포지션 생성, TP/SL 저장")
        assert not pm.has_open_position(SYMBOL), "초기 포지션 없어야 함"
        orders_before = _order_count(engine)
        run_scenario("1", engine, SignalAction.BUY, ENTRY_PRICE)
        orders_after = _order_count(engine)

        if not pm.has_open_position(SYMBOL):
            fail("진입 후 포지션 있어야 함")
        pos = pm.get_position(SYMBOL)
        if not pos or not pos.tp_price or not pos.sl_price:
            fail("포지션에 TP/SL 있어야 함")
        if orders_after <= orders_before:
            fail("BUY 주문 생성됐어야 함")
        ok(f"진입 완료, TP={pos.tp_price:.0f}, SL={pos.sl_price:.0f}")

        # === 시나리오 2: 포지션 보유 + 가격 범위 안 → 주문 없음 ===
        print("\n[시나리오 2] 포지션 보유 + 가격 TP/SL 범위 안 → 주문 없음")
        orders_before = _order_count(engine)
        run_scenario("2", engine, SignalAction.BUY, PRICE_IN_RANGE)
        orders_after = _order_count(engine)

        if not pm.has_open_position(SYMBOL):
            fail("포지션 유지돼야 함")
        if orders_after != orders_before:
            fail(f"주문 생성되면 안 됨 (before={orders_before}, after={orders_after})")
        ok("포지션 유지, 주문 없음")

        # === 시나리오 3: 포지션 보유 + TP 도달 → SELL 청산 ===
        print("\n[시나리오 3] 포지션 보유 + TP 도달 → SELL 청산")
        orders_before = _order_count(engine)
        run_scenario("3", engine, SignalAction.HOLD, TP_PRICE + 1)
        orders_after = _order_count(engine)

        if pm.has_open_position(SYMBOL):
            fail("TP 청산 후 포지션 없어야 함")
        if orders_after <= orders_before:
            fail("SELL 청산 주문 생성됐어야 함")
        ok("TP 청산 완료")

        # === 시나리오 4: 재진입 후 SL 도달 → SELL 청산 ===
        print("\n[시나리오 4] 재진입 후 SL 도달 → SELL 청산")
        run_scenario("4a", engine, SignalAction.BUY, ENTRY_PRICE)
        if not pm.has_open_position(SYMBOL):
            fail("재진입 필요")
        orders_before = _order_count(engine)
        run_scenario("4", engine, SignalAction.HOLD, SL_PRICE - 1)
        orders_after = _order_count(engine)

        if pm.has_open_position(SYMBOL):
            fail("SL 청산 후 포지션 없어야 함")
        if orders_after <= orders_before:
            fail("SELL 청산 주문 생성됐어야 함")
        ok("SL 청산 완료")

        # === 시나리오 5: 포지션 보유 + predictor SELL → 무시 ===
        print("\n[시나리오 5] 포지션 보유 + predictor SELL → 무시", flush=True)
        run_scenario("5a", engine, SignalAction.BUY, ENTRY_PRICE)
        if not pm.has_open_position(SYMBOL):
            fail("재진입 필요")
        orders_before = _order_count(engine)
        run_scenario("5", engine, SignalAction.SELL, PRICE_IN_RANGE)
        orders_after = _order_count(engine)

        if not pm.has_open_position(SYMBOL):
            fail("predictor SELL 무시 시 포지션 유지돼야 함")
        if orders_after != orders_before:
            fail("predictor 기반 청산 주문 생성되면 안 됨")
        ok("predictor SELL 무시, 포지션 유지")

        # === DB 레벨 검증 (DDL 기준) ===
        _verify_db_state(run_id, fail)

        engine.stop()
        print("\n=== MVP 검증 모두 통과 ===", flush=True)
        return 0

    except AssertionError as e:
        print(f"\n검증 실패: {e}", flush=True)
        engine.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
