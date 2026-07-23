"""BINNAIR_* 환경변수 → EngineConfig."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from binnair_trading_engine.config.settings import EngineConfig


def _get(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    return val


def _bool(key: str, default: bool = False) -> bool:
    val = _get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    val = _get(key)
    return int(val) if val is not None else default


def _float(key: str, default: float) -> float:
    val = _get(key)
    return float(val) if val is not None else default


def _float_or_none(key: str) -> float | None:
    val = _get(key)
    if val is None:
        return None
    return float(val)


def _list(key: str, default: list[str] | None = None) -> list[str]:
    val = _get(key)
    if val is None:
        return list(default or ["*"])
    return [part.strip() for part in val.split(",") if part.strip()]


def load_env_file() -> Path | None:
    """
    BINNAIR_ENV_FILE → trade.env (prod) / .env.dev (dev) → .env 순으로 로드.
    Docker compose env_file 은 os.environ 에 직접 주입되므로 파일 없어도 됨.
    """
    explicit = _get("BINNAIR_ENV_FILE") or _get("ENV_FILE")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            load_dotenv(path, override=False)
            return path
        return None

    mode = _get("BINNAIR_ENV", "dev")
    names = (".env.dev", ".env") if mode == "dev" else ("trade.env", ".env")
    for name in names:
        path = Path(name)
        if path.is_file():
            load_dotenv(path, override=False)
            return path
    return None


def config_from_environ() -> EngineConfig:
    """BINNAIR_* 환경변수로 EngineConfig 생성."""
    data: dict = {
        "run_context": {
            "run_id": _get("BINNAIR_RUN_ID", "default_run"),
            "strategy_id": _get("BINNAIR_STRATEGY_ID", "default_strategy"),
            "model_version": _get("BINNAIR_MODEL_VERSION", "timesfm-2.5-200m"),
            "feature_set_version": _get("BINNAIR_FEATURE_SET_VERSION", "price-history-v1"),
            "version": _get("BINNAIR_VERSION", "1.0.0"),
            "user_id": _get("BINNAIR_USER_ID", "default"),
        },
        "market_data": {
            "enabled": _bool("BINNAIR_MARKET_ENABLED", True),
            "provider": _get("BINNAIR_MARKET_PROVIDER", "binance_rest"),
            "symbol": _get("BINNAIR_MARKET_SYMBOL", "BTCUSDT"),
            "poll_interval_seconds": _float("BINNAIR_MARKET_POLL_INTERVAL_SECONDS", 60.0),
            "base_url": _get("BINNAIR_MARKET_BASE_URL", "https://api.binance.com"),
            "timeout": _float("BINNAIR_MARKET_TIMEOUT", 10.0),
        },
        "exchange": {
            "adapter_type": _get("BINNAIR_EXCHANGE_ADAPTER", "binance"),
            "market_type": _get("BINNAIR_EXCHANGE_MARKET_TYPE", "futures"),
            "paper_mode": _bool("BINNAIR_EXCHANGE_PAPER_MODE", True),
            "api_key": _get("BINNAIR_EXCHANGE_API_KEY", ""),
            "api_secret": _get("BINNAIR_EXCHANGE_API_SECRET", ""),
            "base_url": _get("BINNAIR_EXCHANGE_BASE_URL", "https://testnet.binancefuture.com"),
            "leverage": _int("BINNAIR_EXCHANGE_LEVERAGE", 2),
            "margin_type": _get("BINNAIR_EXCHANGE_MARGIN_TYPE", "ISOLATED"),
            "position_side_mode": _get("BINNAIR_EXCHANGE_POSITION_SIDE_MODE", "ONE_WAY"),
            "oco_enabled": _bool("BINNAIR_EXCHANGE_OCO_ENABLED", False),
        },
        "storage": {
            "backend": _get("BINNAIR_STORAGE_BACKEND", "postgres"),
            "host": _get("BINNAIR_STORAGE_HOST", "localhost"),
            "port": _int("BINNAIR_STORAGE_PORT", 5432),
            "dbname": _get("BINNAIR_STORAGE_DBNAME", "binnair"),
            "user": _get("BINNAIR_STORAGE_USER", "binnair"),
            "password": _get("BINNAIR_STORAGE_PASSWORD", ""),
            "schema": _get("BINNAIR_STORAGE_SCHEMA", "trade"),
        },
        "trade_rules": {
            "tp_pct": _float("BINNAIR_TRADE_TP_PCT", 0.01),
            "sl_pct": _float("BINNAIR_TRADE_SL_PCT", 0.005),
        },
        "sizing": {
            "quote_asset": _get("BINNAIR_SIZING_QUOTE_ASSET", "USDT"),
            "risk_per_trade_pct": _float("BINNAIR_SIZING_RISK_PER_TRADE_PCT", 0.005),
            "max_position_notional_pct": _float("BINNAIR_SIZING_MAX_POSITION_NOTIONAL_PCT", 0.20),
            "min_order_notional_usdt": _float("BINNAIR_SIZING_MIN_ORDER_NOTIONAL_USDT", 5.0),
            "max_leverage": _int("BINNAIR_SIZING_MAX_LEVERAGE", 2),
            "fallback_equity_usdt": _float("BINNAIR_SIZING_FALLBACK_EQUITY_USDT", 0.0),
        },
        "risk": {
            "max_position_notional_pct": _float("BINNAIR_RISK_MAX_POSITION_NOTIONAL_PCT", 0.20),
            "max_position_qty": _float("BINNAIR_RISK_MAX_POSITION_QTY", 0.0),
            "daily_loss_limit_pct": _float("BINNAIR_RISK_DAILY_LOSS_LIMIT_PCT", 0.03),
            "duplicate_order_window_seconds": _int("BINNAIR_RISK_DUPLICATE_ORDER_WINDOW_SECONDS", 180),
            "min_hold_seconds_before_signal_exit": _int(
                "BINNAIR_RISK_MIN_HOLD_SECONDS_BEFORE_SIGNAL_EXIT", 90
            ),
            "max_consecutive_losses": _int("BINNAIR_RISK_MAX_CONSECUTIVE_LOSSES", 3),
            "consecutive_loss_pause_minutes": _int(
                "BINNAIR_RISK_CONSECUTIVE_LOSS_PAUSE_MINUTES", 30
            ),
        },
        "signal_policy": {
            "consecutive_required": _int("BINNAIR_SIGNAL_CONSECUTIVE_REQUIRED", 2),
            "mode": _get("BINNAIR_SIGNAL_MODE", "long_only"),
        },
        "predictor_type": _get("BINNAIR_PREDICTOR_TYPE", "timesfm"),
        "predictor_config": {
            "timesfm": {
                "model_id": _get("BINNAIR_TIMESFM_MODEL_ID", "google/timesfm-2.5-200m-pytorch"),
                "use_ohlcv_history": _bool("BINNAIR_TIMESFM_USE_OHLCV_HISTORY", True),
                "timeframe": _get("BINNAIR_TIMESFM_TIMEFRAME", "1m"),
                "context_length": _int("BINNAIR_TIMESFM_CONTEXT_LENGTH", 128),
                "min_context": _int("BINNAIR_TIMESFM_MIN_CONTEXT", 64),
                "horizon": _int("BINNAIR_TIMESFM_HORIZON", 3),
                "forecast_mode": _get("BINNAIR_TIMESFM_FORECAST_MODE", "average"),
                "forecast_index": _int("BINNAIR_TIMESFM_FORECAST_INDEX", -1),
                "fee_rate": _float("BINNAIR_TIMESFM_FEE_RATE", 0.0004),
                "slippage_rate": _float("BINNAIR_TIMESFM_SLIPPAGE_RATE", 0.0005),
                "safety_margin": _float("BINNAIR_TIMESFM_SAFETY_MARGIN", 0.0001),
                "signal_threshold": _float_or_none("BINNAIR_TIMESFM_SIGNAL_THRESHOLD"),
                "exit_signal_threshold": _float_or_none("BINNAIR_TIMESFM_EXIT_SIGNAL_THRESHOLD"),
                "exit_threshold_mult": _float("BINNAIR_TIMESFM_EXIT_THRESHOLD_MULT", 0.85),
                "timeframe_threshold_scale": _bool("BINNAIR_TIMESFM_TIMEFRAME_THRESHOLD_SCALE", True),
                "ref_timeframe": _get("BINNAIR_TIMESFM_REF_TIMEFRAME", "1m"),
                "ref_horizon": _int("BINNAIR_TIMESFM_REF_HORIZON", 3),
                "min_threshold_fee_ratio": _float("BINNAIR_TIMESFM_MIN_THRESHOLD_FEE_RATIO", 0.25),
                "predict_on_candle_close": _bool("BINNAIR_TIMESFM_PREDICT_ON_CANDLE_CLOSE", True),
                "append_live_price_to_history": _bool(
                    "BINNAIR_TIMESFM_APPEND_LIVE_PRICE_TO_HISTORY", False
                ),
                "model_version": _get("BINNAIR_TIMESFM_MODEL_VERSION", "timesfm-2.5-200m"),
                "feature_set_version": _get("BINNAIR_TIMESFM_FEATURE_SET_VERSION", "price-history-v1"),
            }
        },
        "risk_enabled": _bool("BINNAIR_RISK_ENABLED", True),
        "state_persist_path": _get("BINNAIR_STATE_PERSIST_PATH"),
        "log_level": _get("BINNAIR_LOG_LEVEL", "INFO"),
        "persist_model_inference": _bool("BINNAIR_PERSIST_MODEL_INFERENCE", False),
        "flatten_on_shutdown": _bool("BINNAIR_FLATTEN_ON_SHUTDOWN", True),
        "api": {
            "enabled": _bool("BINNAIR_API_ENABLED", True),
            "host": _get("BINNAIR_API_HOST", "127.0.0.1"),
            "port": _int("BINNAIR_API_PORT", 8000),
            "cors_origins": _list("BINNAIR_API_CORS_ORIGINS"),
            "live_stream": {
                "enabled": _bool("BINNAIR_API_LIVE_STREAM_ENABLED", True),
                "mark_price_enabled": _bool("BINNAIR_API_MARK_PRICE_ENABLED", True),
                "listen_key_keepalive_seconds": _int("BINNAIR_API_LISTEN_KEY_KEEPALIVE_SECONDS", 1800),
                "reconnect_delay_seconds": _float("BINNAIR_API_RECONNECT_DELAY_SECONDS", 5.0),
            },
        },
        "autopilot": {
            "enabled": _bool("BINNAIR_AUTOPILOT_ENABLED", False),
            "score_window": _int("BINNAIR_AUTOPILOT_SCORE_WINDOW", 500),
            "score_min_samples": _int("BINNAIR_AUTOPILOT_SCORE_MIN_SAMPLES", 30),
            "score_percentile": _float("BINNAIR_AUTOPILOT_SCORE_PERCENTILE", 70.0),
            "score_k": _float("BINNAIR_AUTOPILOT_SCORE_K", 1.0),
            "atr_period": _int("BINNAIR_AUTOPILOT_ATR_PERIOD", 14),
            "ema_fast": _int("BINNAIR_AUTOPILOT_EMA_FAST", 12),
            "ema_slow": _int("BINNAIR_AUTOPILOT_EMA_SLOW", 26),
            "vol_lookback": _int("BINNAIR_AUTOPILOT_VOL_LOOKBACK", 100),
            "high_vol_ratio": _float("BINNAIR_AUTOPILOT_HIGH_VOL_RATIO", 1.35),
            "low_vol_ratio": _float("BINNAIR_AUTOPILOT_LOW_VOL_RATIO", 0.75),
            "trend_slope_threshold": _float(
                "BINNAIR_AUTOPILOT_TREND_SLOPE_THRESHOLD", 0.0015
            ),
            "high_vol_position_scale": _float(
                "BINNAIR_AUTOPILOT_HIGH_VOL_POSITION_SCALE", 0.5
            ),
            "high_vol_consecutive_delta": _int(
                "BINNAIR_AUTOPILOT_HIGH_VOL_CONSECUTIVE_DELTA", 2
            ),
            "high_vol_threshold_mult": _float(
                "BINNAIR_AUTOPILOT_HIGH_VOL_THRESHOLD_MULT", 1.5
            ),
            "base_tp_atr_mult": _float("BINNAIR_AUTOPILOT_BASE_TP_ATR_MULT", 2.0),
            "base_sl_atr_mult": _float("BINNAIR_AUTOPILOT_BASE_SL_ATR_MULT", 1.2),
            "base_consecutive_required": _int(
                "BINNAIR_AUTOPILOT_BASE_CONSECUTIVE_REQUIRED",
                _int("BINNAIR_SIGNAL_CONSECUTIVE_REQUIRED", 2),
            ),
            "status_log_every_ticks": _int("BINNAIR_AUTOPILOT_STATUS_LOG_EVERY_TICKS", 10),
        },
    }
    cfg = EngineConfig.from_dict(data)
    cfg = _apply_timesfm_market_defaults(cfg)
    return _validate_signal_mode(cfg)


_VALID_SIGNAL_MODES = frozenset({"long_only", "long_short"})


def _validate_signal_mode(cfg: EngineConfig) -> EngineConfig:
    mode = (cfg.signal_policy.mode or "long_only").strip().lower()
    if mode not in _VALID_SIGNAL_MODES:
        raise ValueError(
            f"Invalid BINNAIR_SIGNAL_MODE={mode!r}; "
            f"allowed: {', '.join(sorted(_VALID_SIGNAL_MODES))}"
        )
    cfg.signal_policy.mode = mode
    return cfg


def _apply_timesfm_market_defaults(cfg: EngineConfig) -> EngineConfig:
    """TimesFM timeframe과 market poll interval 정렬."""
    if cfg.predictor_type != "timesfm" or cfg.predictor_timesfm_config is None:
        return cfg
    if not _bool("BINNAIR_MARKET_ALIGN_POLL_WITH_TIMEFRAME", True):
        return cfg
    from binnair_trading_engine.market_data.timeframe import timeframe_to_seconds

    tf_sec = timeframe_to_seconds(cfg.predictor_timesfm_config.timeframe)
    poll = cfg.market_data.poll_interval_seconds
    if poll < tf_sec:
        cfg.market_data.poll_interval_seconds = float(tf_sec)
    return cfg
