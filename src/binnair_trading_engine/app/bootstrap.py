"""
설정값을 읽어 자동매매 엔진의 의존성을 조립한다.
exchange, predictor, strategy, risk, storage, signal policy를 생성해 TradingEngine에 주입한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from binnair_trading_engine.autopilot import AutopilotController
from binnair_trading_engine.config import load_config
from binnair_trading_engine.engine import TradingEngine
from binnair_trading_engine.domain.models import EngineContext
from binnair_trading_engine.exchange import create_exchange
from binnair_trading_engine.market_data import create_price_history_provider
from binnair_trading_engine.position import PositionManager
from binnair_trading_engine.predictor import create_predictor
from binnair_trading_engine.risk import create_risk_checker
from binnair_trading_engine.signal import ConsecutiveSignalPolicy
from binnair_trading_engine.state import create_state_manager
from binnair_trading_engine.storage import create_storage
from binnair_trading_engine.strategy import create_strategy
from binnair_trading_engine.strategy.exit_manager import ExitManager

logger = logging.getLogger(__name__)


def bootstrap() -> TradingEngine:
    """
    설정 로드 후 엔진 인스턴스 생성.
    paper_trading=True 가 기본값.
    """
    config = load_config()
    runtime_state = None
    if config.storage.backend == "postgres":
        from binnair_trading_engine.config.runtime_loader import apply_runtime_overlay

        config, runtime_state = apply_runtime_overlay(
            config, user_id=config.run_context.user_id
        )
    rc = config.run_context
    ctx = EngineContext(
        version=rc.version,
        run_id=rc.run_id,
        strategy_id=rc.strategy_id,
        model_version=rc.model_version,
        feature_set_version=rc.feature_set_version,
        user_id=rc.user_id,
    )

    exchange = create_exchange(config)
    price_history_provider = create_price_history_provider(config)
    predictor = create_predictor(config, price_history_provider=price_history_provider)
    risk = create_risk_checker(config, exchange=exchange)
    storage = create_storage(config)
    state_manager = create_state_manager(config)
    strategy = create_strategy(config, exchange=exchange)
    position_manager = PositionManager(run_id=rc.run_id)
    exit_manager = ExitManager()
    signal_policy = ConsecutiveSignalPolicy(
        consecutive_required=config.signal_policy.consecutive_required,
        mode=config.signal_policy.mode,
    )

    autopilot: AutopilotController | None = None
    if config.autopilot.enabled:
        autopilot = AutopilotController(
            config=config.autopilot,
            timesfm_config=config.predictor_timesfm_config,
            price_history_provider=price_history_provider,
            state_persist_path=config.state_persist_path,
        )
        autopilot.initialize(
            run_id=rc.run_id,
            user_id=rc.user_id,
            symbol=config.market_data.symbol,
            storage_backend=config.storage.backend,
        )
        logger.info(
            "Autopilot enabled (score_window=%d, base_tp_atr=%.1f, base_sl_atr=%.1f)",
            config.autopilot.score_window,
            config.autopilot.base_tp_atr_mult,
            config.autopilot.base_sl_atr_mult,
        )

    engine = TradingEngine(
        config=config,
        ctx=ctx,
        exchange=exchange,
        predictor=predictor,
        risk_checker=risk,
        strategy=strategy,
        storage=storage,
        state_manager=state_manager,
        position_manager=position_manager,
        exit_manager=exit_manager,
        signal_policy=signal_policy,
        autopilot=autopilot,
    )
    if config.storage.backend == "postgres":
        enabled = runtime_state.trading_enabled if runtime_state else False
        engine.set_trading_enabled(enabled)
    return engine
