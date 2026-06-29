#!/usr/bin/env python3
"""
샘플 실행: market tick -> signal -> risk -> order -> execution -> persistence
설정된 Predictor로 1회 tick 처리 검증.
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.app.bootstrap import bootstrap
from binnair_trading_engine.domain.models import MarketSnapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)


def main() -> int:
    engine = bootstrap()
    run_id = engine._ctx.run_id

    engine.start()

    # 1. Market snapshot 시뮬레이션
    # TimesFM은 충분한 가격 히스토리가 쌓이기 전까지 HOLD를 반환한다.
    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        price=50000.0,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        correlation_id=str(uuid.uuid4()),
    )

    # 2. 한 틱 처리 (signal evaluation -> risk -> order -> execution -> persistence)
    engine.run_cycle(snapshot)

    engine.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
