"""엔진 부트스트랩: 설정 로드, 의존성 주입, 엔진 인스턴스 생성."""

from __future__ import annotations

import logging
from pathlib import Path

from binnair_trading_engine.config import load_config
from binnair_trading_engine.engine import TradingEngine
from binnair_trading_engine.domain.models import EngineContext
from binnair_trading_engine.exchange import create_exchange
from binnair_trading_engine.predictor import create_predictor
from binnair_trading_engine.risk import create_risk_checker
from binnair_trading_engine.state import create_state_manager
from binnair_trading_engine.storage import create_storage
from binnair_trading_engine.strategy import create_strategy

logger = logging.getLogger(__name__)


def bootstrap(config_path: str | Path | None = None) -> TradingEngine:
    """
    설정 로드 후 엔진 인스턴스 생성.
    paper_trading=True 가 기본값.
    """
    config = load_config(config_path)
    rc = config.run_context
    ctx = EngineContext(
        version=rc.version,
        run_id=rc.run_id,
        strategy_id=rc.strategy_id,
        model_version=rc.model_version,
        feature_set_version=rc.feature_set_version,
    )

    exchange = create_exchange(config)
    predictor = create_predictor(config)
    risk = create_risk_checker(config)
    storage = create_storage(config)
    state_manager = create_state_manager(config)
    strategy = create_strategy(config)

    engine = TradingEngine(
        config=config,
        ctx=ctx,
        exchange=exchange,
        predictor=predictor,
        risk_checker=risk,
        strategy=strategy,
        storage=storage,
        state_manager=state_manager,
    )
    return engine
