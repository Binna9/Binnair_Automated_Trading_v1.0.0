"""
UI 런타임 설정 (L1) — trade.env(L0)와 병합.

API는 L1 전체 필드를 받는다. GET /control/schema 의 tier 로
UI 기본/고급 폼 노출을 구분한다. 비밀키·DB·API 서버는 env 전용.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from binnair_trading_engine.autopilot.models import AutopilotConfig
from binnair_trading_engine.config.settings import EngineConfig

ParamTier = Literal["basic", "advanced"]

# 기본 화면에 보여줄 필드 (나머지는 고급 모드)
BASIC_PARAM_KEYS: tuple[str, ...] = (
    "symbol",
    "signal_mode",
    "signal_consecutive_required",
    "timesfm_timeframe",
    "leverage",
    "autopilot_enabled",
    "autopilot_score_percentile",
    "trade_tp_pct",
    "trade_sl_pct",
)

# 하위 호환
UI_PARAM_KEYS = BASIC_PARAM_KEYS


class RuntimeConfigParams(BaseModel):
    """UI start/save body — L1 전체 (전부 optional)."""

    # run context (고급)
    run_id: str | None = Field(default=None, max_length=128)
    strategy_id: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=64)
    feature_set_version: str | None = Field(default=None, max_length=64)

    # market
    symbol: str | None = Field(default=None, max_length=32)
    poll_interval_seconds: float | None = Field(default=None, gt=0)

    # exchange (비밀키 제외)
    leverage: int | None = Field(default=None, ge=1, le=125)
    margin_type: str | None = Field(default=None, pattern=r"^(ISOLATED|CROSSED)$")
    position_side_mode: str | None = Field(default=None, pattern=r"^(ONE_WAY|HEDGE)$")
    oco_enabled: bool | None = None

    # trade rules
    trade_tp_pct: float | None = Field(default=None, ge=0)
    trade_sl_pct: float | None = Field(default=None, ge=0)

    # sizing (고급)
    sizing_risk_per_trade_pct: float | None = Field(default=None, gt=0, le=1)
    sizing_max_position_notional_pct: float | None = Field(default=None, gt=0, le=1)
    sizing_min_order_notional_usdt: float | None = Field(default=None, ge=0)
    sizing_max_leverage: int | None = Field(default=None, ge=1)

    # risk (고급)
    risk_max_position_notional_pct: float | None = Field(default=None, gt=0, le=1)
    risk_daily_loss_limit_pct: float | None = Field(default=None, gt=0, le=1)
    risk_duplicate_order_window_seconds: int | None = Field(default=None, ge=0)
    risk_min_hold_seconds_before_signal_exit: int | None = Field(default=None, ge=0)
    risk_max_consecutive_losses: int | None = Field(default=None, ge=0)
    risk_consecutive_loss_pause_minutes: int | None = Field(default=None, ge=0)
    risk_enabled: bool | None = None
    flatten_on_shutdown: bool | None = None

    # signal policy
    signal_mode: str | None = Field(default=None, pattern=r"^(long_only|long_short)$")
    signal_consecutive_required: int | None = Field(default=None, ge=1)

    # timesfm
    timesfm_timeframe: str | None = Field(default=None, max_length=8)
    timesfm_forecast_mode: str | None = Field(default=None, pattern=r"^(average|last)$")
    timesfm_horizon: int | None = Field(default=None, ge=1, le=32)
    timesfm_signal_threshold: float | None = Field(default=None, ge=0)
    timesfm_exit_signal_threshold: float | None = Field(default=None, ge=0)
    timesfm_exit_threshold_mult: float | None = Field(default=None, gt=0)
    timesfm_timeframe_threshold_scale: bool | None = None
    timesfm_predict_on_candle_close: bool | None = None
    timesfm_fee_rate: float | None = Field(default=None, ge=0)
    timesfm_slippage_rate: float | None = Field(default=None, ge=0)
    timesfm_safety_margin: float | None = Field(default=None, ge=0)

    # autopilot
    autopilot_enabled: bool | None = None
    autopilot_score_percentile: float | None = Field(default=None, ge=0, le=100)
    autopilot_score_k: float | None = Field(default=None, ge=0)
    autopilot_base_tp_atr_mult: float | None = Field(default=None, gt=0)
    autopilot_base_sl_atr_mult: float | None = Field(default=None, gt=0)
    autopilot_base_consecutive_required: int | None = Field(default=None, ge=1)
    autopilot_atr_period: int | None = Field(default=None, ge=2)
    autopilot_vol_lookback: int | None = Field(default=None, ge=10)

    @field_validator("timesfm_timeframe")
    @classmethod
    def _validate_timeframe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re

        if not re.match(r"^\d+[mhdw]$", v.lower()):
            raise ValueError("timesfm_timeframe must match e.g. 1m, 5m, 1h")
        return v.lower()

    def to_patch_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


UIControlParams = RuntimeConfigParams


def _schema_entry(
    key: str,
    *,
    group: str,
    type_: str,
    label: str,
    tier: ParamTier,
    **extra: Any,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "key": key,
        "group": group,
        "type": type_,
        "label": label,
        "tier": tier,
    }
    entry.update(extra)
    return entry


RUNTIME_PARAM_SCHEMA: list[dict[str, Any]] = [
    _schema_entry("symbol", group="market", type_="string", label="거래 심볼", tier="basic", example="XRPUSDT"),
    _schema_entry("signal_mode", group="signal", type_="enum", label="매매 모드", tier="basic", options=["long_only", "long_short"]),
    _schema_entry("signal_consecutive_required", group="signal", type_="int", label="연속 신호 횟수", tier="basic", min=1),
    _schema_entry("timesfm_timeframe", group="timesfm", type_="string", label="캔들 주기", tier="basic", example="5m", hint="변경 시 서버 재시작 권장"),
    _schema_entry("leverage", group="exchange", type_="int", label="레버리지", tier="basic", min=1, max=125),
    _schema_entry("autopilot_enabled", group="autopilot", type_="bool", label="Autopilot", tier="basic"),
    _schema_entry("autopilot_score_percentile", group="autopilot", type_="number", label="진입 민감도", tier="basic", min=0, max=100, hint="Autopilot on"),
    _schema_entry("trade_tp_pct", group="trade", type_="number", label="익절 %", tier="basic", hint="Autopilot off"),
    _schema_entry("trade_sl_pct", group="trade", type_="number", label="손절 %", tier="basic", hint="Autopilot off"),
    _schema_entry("poll_interval_seconds", group="market", type_="number", label="Tick 간격(초)", tier="advanced", min=1),
    _schema_entry("margin_type", group="exchange", type_="enum", label="마진 타입", tier="advanced", options=["ISOLATED", "CROSSED"]),
    _schema_entry("position_side_mode", group="exchange", type_="enum", label="포지션 모드", tier="advanced", options=["ONE_WAY", "HEDGE"]),
    _schema_entry("oco_enabled", group="exchange", type_="bool", label="OCO 보호주문", tier="advanced"),
    _schema_entry("run_id", group="run", type_="string", label="Run ID", tier="advanced"),
    _schema_entry("strategy_id", group="run", type_="string", label="Strategy ID", tier="advanced"),
    _schema_entry("model_version", group="run", type_="string", label="Model version", tier="advanced"),
    _schema_entry("feature_set_version", group="run", type_="string", label="Feature set version", tier="advanced"),
    _schema_entry("sizing_risk_per_trade_pct", group="sizing", type_="number", label="거래당 리스크 %", tier="advanced"),
    _schema_entry("sizing_max_position_notional_pct", group="sizing", type_="number", label="최대 포지션 %", tier="advanced"),
    _schema_entry("sizing_min_order_notional_usdt", group="sizing", type_="number", label="최소 주문(USDT)", tier="advanced"),
    _schema_entry("sizing_max_leverage", group="sizing", type_="int", label="사이징 레버리지 상한", tier="advanced"),
    _schema_entry("risk_max_position_notional_pct", group="risk", type_="number", label="포지션 명목 상한 %", tier="advanced"),
    _schema_entry("risk_daily_loss_limit_pct", group="risk", type_="number", label="일일 손실 한도 %", tier="advanced"),
    _schema_entry("risk_duplicate_order_window_seconds", group="risk", type_="int", label="중복 주문 방지(초)", tier="advanced"),
    _schema_entry("risk_min_hold_seconds_before_signal_exit", group="risk", type_="int", label="최소 보유(초)", tier="advanced"),
    _schema_entry("risk_max_consecutive_losses", group="risk", type_="int", label="연속 손절 한도", tier="advanced"),
    _schema_entry("risk_consecutive_loss_pause_minutes", group="risk", type_="int", label="손절 후 휴식(분)", tier="advanced"),
    _schema_entry("risk_enabled", group="risk", type_="bool", label="리스크 체크", tier="advanced"),
    _schema_entry("flatten_on_shutdown", group="risk", type_="bool", label="종료 시 청산", tier="advanced"),
    _schema_entry("timesfm_forecast_mode", group="timesfm", type_="enum", label="Forecast 모드", tier="advanced", options=["average", "last"]),
    _schema_entry("timesfm_horizon", group="timesfm", type_="int", label="Horizon", tier="advanced", min=1, max=32),
    _schema_entry("timesfm_signal_threshold", group="timesfm", type_="number", label="진입 threshold", tier="advanced", hint="null=Autopilot"),
    _schema_entry("timesfm_exit_signal_threshold", group="timesfm", type_="number", label="청산 threshold", tier="advanced"),
    _schema_entry("timesfm_exit_threshold_mult", group="timesfm", type_="number", label="청산 threshold 배수", tier="advanced"),
    _schema_entry("timesfm_timeframe_threshold_scale", group="timesfm", type_="bool", label="TF threshold 스케일", tier="advanced"),
    _schema_entry("timesfm_predict_on_candle_close", group="timesfm", type_="bool", label="캔들 close 시만 예측", tier="advanced"),
    _schema_entry("timesfm_fee_rate", group="timesfm", type_="number", label="수수료율", tier="advanced"),
    _schema_entry("timesfm_slippage_rate", group="timesfm", type_="number", label="슬리피지율", tier="advanced"),
    _schema_entry("timesfm_safety_margin", group="timesfm", type_="number", label="안전 마진", tier="advanced"),
    _schema_entry("autopilot_score_k", group="autopilot", type_="number", label="Score K", tier="advanced"),
    _schema_entry("autopilot_base_tp_atr_mult", group="autopilot", type_="number", label="TP ATR 배수", tier="advanced"),
    _schema_entry("autopilot_base_sl_atr_mult", group="autopilot", type_="number", label="SL ATR 배수", tier="advanced"),
    _schema_entry("autopilot_base_consecutive_required", group="autopilot", type_="int", label="기본 consecutive", tier="advanced"),
    _schema_entry("autopilot_atr_period", group="autopilot", type_="int", label="ATR 기간", tier="advanced"),
    _schema_entry("autopilot_vol_lookback", group="autopilot", type_="int", label="변동성 lookback", tier="advanced"),
]

ADVANCED_PARAM_KEYS: tuple[str, ...] = tuple(
    e["key"] for e in RUNTIME_PARAM_SCHEMA if e["tier"] == "advanced"
)

RUNTIME_PARAM_KEYS: tuple[str, ...] = tuple(e["key"] for e in RUNTIME_PARAM_SCHEMA)

ENV_ONLY_KEYS: list[str] = [
    "exchange.api_key",
    "exchange.api_secret",
    "exchange.base_url",
    "exchange.paper_mode",
    "exchange.adapter_type",
    "exchange.market_type",
    "storage",
    "api",
    "predictor_timesfm.model_id",
    "predictor_timesfm.context_length",
    "predictor_timesfm.min_context",
    "predictor_timesfm.use_ohlcv_history",
    "state_persist_path",
    "sizing.quote_asset",
    "sizing.fallback_equity_usdt",
    "risk.max_position_qty",
    "autopilot.score_window",
    "autopilot.score_min_samples",
    "autopilot.ema_fast",
    "autopilot.ema_slow",
    "autopilot.high_vol_ratio",
    "autopilot.low_vol_ratio",
    "autopilot.trend_slope_threshold",
    "autopilot.status_log_every_ticks",
]


def engine_config_to_nested_dict(cfg: EngineConfig) -> dict[str, Any]:
    """EngineConfig → env_loader 호환 nested dict."""
    tfm = cfg.predictor_timesfm_config
    ap = cfg.autopilot
    return {
        "run_context": asdict(cfg.run_context),
        "exchange": {
            "adapter_type": cfg.exchange.adapter_type,
            "market_type": cfg.exchange.market_type,
            "paper_mode": cfg.exchange.paper_mode,
            "api_key": cfg.exchange.api_key,
            "api_secret": cfg.exchange.api_secret,
            "base_url": cfg.exchange.base_url,
            "leverage": cfg.exchange.leverage,
            "margin_type": cfg.exchange.margin_type,
            "position_side_mode": cfg.exchange.position_side_mode,
            "oco_enabled": cfg.exchange.oco_enabled,
        },
        "storage": asdict(cfg.storage),
        "market_data": asdict(cfg.market_data),
        "trade_rules": asdict(cfg.trade_rules),
        "sizing": asdict(cfg.sizing),
        "risk": asdict(cfg.risk),
        "signal_policy": asdict(cfg.signal_policy),
        "predictor_type": cfg.predictor_type,
        "predictor_config": {
            "timesfm": asdict(tfm) if tfm else {},
        },
        "risk_enabled": cfg.risk_enabled,
        "state_persist_path": str(cfg.state_persist_path) if cfg.state_persist_path else None,
        "log_level": cfg.log_level,
        "persist_model_inference": cfg.persist_model_inference,
        "flatten_on_shutdown": cfg.flatten_on_shutdown,
        "api": {
            "enabled": cfg.api.enabled,
            "host": cfg.api.host,
            "port": cfg.api.port,
            "cors_origins": cfg.api.cors_origins,
            "live_stream": asdict(cfg.api.live_stream),
        },
        "autopilot": asdict(ap),
    }


def runtime_patch_to_nested(patch: dict[str, Any]) -> dict[str, Any]:
    """flat runtime patch → EngineConfig.from_dict partial nested."""
    out: dict[str, Any] = {}
    if "run_id" in patch:
        out.setdefault("run_context", {})["run_id"] = patch["run_id"]
    if "strategy_id" in patch:
        out.setdefault("run_context", {})["strategy_id"] = patch["strategy_id"]
    if "model_version" in patch:
        out.setdefault("run_context", {})["model_version"] = patch["model_version"]
    if "feature_set_version" in patch:
        out.setdefault("run_context", {})["feature_set_version"] = patch["feature_set_version"]

    md: dict[str, Any] = {}
    if "symbol" in patch:
        md["symbol"] = patch["symbol"]
    if "poll_interval_seconds" in patch:
        md["poll_interval_seconds"] = patch["poll_interval_seconds"]
    if md:
        out["market_data"] = md

    exc: dict[str, Any] = {}
    for k, nk in [
        ("leverage", "leverage"),
        ("margin_type", "margin_type"),
        ("position_side_mode", "position_side_mode"),
        ("oco_enabled", "oco_enabled"),
    ]:
        if k in patch:
            exc[nk] = patch[k]
    if exc:
        out["exchange"] = exc

    tr: dict[str, Any] = {}
    if "trade_tp_pct" in patch:
        tr["tp_pct"] = patch["trade_tp_pct"]
    if "trade_sl_pct" in patch:
        tr["sl_pct"] = patch["trade_sl_pct"]
    if tr:
        out["trade_rules"] = tr

    sizing_map = {
        "sizing_risk_per_trade_pct": "risk_per_trade_pct",
        "sizing_max_position_notional_pct": "max_position_notional_pct",
        "sizing_min_order_notional_usdt": "min_order_notional_usdt",
        "sizing_max_leverage": "max_leverage",
    }
    sz: dict[str, Any] = {}
    for pk, nk in sizing_map.items():
        if pk in patch:
            sz[nk] = patch[pk]
    if sz:
        out["sizing"] = sz

    risk_map = {
        "risk_max_position_notional_pct": "max_position_notional_pct",
        "risk_daily_loss_limit_pct": "daily_loss_limit_pct",
        "risk_duplicate_order_window_seconds": "duplicate_order_window_seconds",
        "risk_min_hold_seconds_before_signal_exit": "min_hold_seconds_before_signal_exit",
        "risk_max_consecutive_losses": "max_consecutive_losses",
        "risk_consecutive_loss_pause_minutes": "consecutive_loss_pause_minutes",
    }
    rk: dict[str, Any] = {}
    for pk, nk in risk_map.items():
        if pk in patch:
            rk[nk] = patch[pk]
    if rk:
        out["risk"] = rk
    if "risk_enabled" in patch:
        out["risk_enabled"] = patch["risk_enabled"]
    if "flatten_on_shutdown" in patch:
        out["flatten_on_shutdown"] = patch["flatten_on_shutdown"]

    sp: dict[str, Any] = {}
    if "signal_mode" in patch:
        sp["mode"] = patch["signal_mode"]
    if "signal_consecutive_required" in patch:
        sp["consecutive_required"] = patch["signal_consecutive_required"]
    if sp:
        out["signal_policy"] = sp

    tfm_map = {
        "timesfm_timeframe": "timeframe",
        "timesfm_forecast_mode": "forecast_mode",
        "timesfm_horizon": "horizon",
        "timesfm_signal_threshold": "signal_threshold",
        "timesfm_exit_signal_threshold": "exit_signal_threshold",
        "timesfm_exit_threshold_mult": "exit_threshold_mult",
        "timesfm_timeframe_threshold_scale": "timeframe_threshold_scale",
        "timesfm_predict_on_candle_close": "predict_on_candle_close",
        "timesfm_fee_rate": "fee_rate",
        "timesfm_slippage_rate": "slippage_rate",
        "timesfm_safety_margin": "safety_margin",
    }
    tfm: dict[str, Any] = {}
    for pk, nk in tfm_map.items():
        if pk in patch:
            tfm[nk] = patch[pk]
    if tfm:
        out.setdefault("predictor_config", {})["timesfm"] = tfm

    ap_map = {
        "autopilot_enabled": "enabled",
        "autopilot_score_percentile": "score_percentile",
        "autopilot_score_k": "score_k",
        "autopilot_base_tp_atr_mult": "base_tp_atr_mult",
        "autopilot_base_sl_atr_mult": "base_sl_atr_mult",
        "autopilot_base_consecutive_required": "base_consecutive_required",
        "autopilot_atr_period": "atr_period",
        "autopilot_vol_lookback": "vol_lookback",
    }
    ap: dict[str, Any] = {}
    for pk, nk in ap_map.items():
        if pk in patch:
            ap[nk] = patch[pk]
    if ap:
        out["autopilot"] = ap

    return out


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, val in patch.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(val, dict)
        ):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = copy.deepcopy(val)
    return merged


def merge_runtime_config(base: EngineConfig, patch: dict[str, Any]) -> EngineConfig:
    """env 기반 EngineConfig + UI runtime patch → 새 EngineConfig."""
    from binnair_trading_engine.config.env_loader import (
        _apply_timesfm_market_defaults,
        _validate_signal_mode,
    )

    nested_patch = runtime_patch_to_nested(patch)
    merged = _deep_merge(engine_config_to_nested_dict(base), nested_patch)
    cfg = EngineConfig.from_dict(merged)
    cfg = _apply_timesfm_market_defaults(cfg)
    return _validate_signal_mode(cfg)


def engine_config_to_ui_params(cfg: EngineConfig) -> dict[str, Any]:
    """기본 화면용 effective 값 (tier=basic)."""
    full = engine_config_to_runtime_params(cfg)
    return {k: full[k] for k in BASIC_PARAM_KEYS if k in full}


def split_config_tiers(cfg: EngineConfig) -> dict[str, dict[str, Any]]:
    """GET /config 응답용 — basic / advanced / full."""
    full = engine_config_to_runtime_params(cfg)
    return {
        "basic": {k: full[k] for k in BASIC_PARAM_KEYS if k in full},
        "advanced": {k: full[k] for k in ADVANCED_PARAM_KEYS if k in full},
        "full": full,
    }


def engine_config_to_runtime_params(cfg: EngineConfig) -> dict[str, Any]:
    """현재 effective 설정을 UI flat dict로 (env+runtime 반영 후)."""
    tfm = cfg.predictor_timesfm_config
    ap = cfg.autopilot
    return {
        "run_id": cfg.run_context.run_id,
        "strategy_id": cfg.run_context.strategy_id,
        "model_version": cfg.run_context.model_version,
        "feature_set_version": cfg.run_context.feature_set_version,
        "symbol": cfg.market_data.symbol,
        "poll_interval_seconds": cfg.market_data.poll_interval_seconds,
        "leverage": cfg.exchange.leverage,
        "margin_type": cfg.exchange.margin_type,
        "position_side_mode": cfg.exchange.position_side_mode,
        "oco_enabled": cfg.exchange.oco_enabled,
        "trade_tp_pct": cfg.trade_rules.tp_pct,
        "trade_sl_pct": cfg.trade_rules.sl_pct,
        "sizing_risk_per_trade_pct": cfg.sizing.risk_per_trade_pct,
        "sizing_max_position_notional_pct": cfg.sizing.max_position_notional_pct,
        "sizing_min_order_notional_usdt": cfg.sizing.min_order_notional_usdt,
        "sizing_max_leverage": cfg.sizing.max_leverage,
        "risk_max_position_notional_pct": cfg.risk.max_position_notional_pct,
        "risk_daily_loss_limit_pct": cfg.risk.daily_loss_limit_pct,
        "risk_duplicate_order_window_seconds": cfg.risk.duplicate_order_window_seconds,
        "risk_min_hold_seconds_before_signal_exit": cfg.risk.min_hold_seconds_before_signal_exit,
        "risk_max_consecutive_losses": cfg.risk.max_consecutive_losses,
        "risk_consecutive_loss_pause_minutes": cfg.risk.consecutive_loss_pause_minutes,
        "risk_enabled": cfg.risk_enabled,
        "flatten_on_shutdown": cfg.flatten_on_shutdown,
        "signal_mode": cfg.signal_policy.mode,
        "signal_consecutive_required": cfg.signal_policy.consecutive_required,
        "timesfm_timeframe": tfm.timeframe if tfm else "1m",
        "timesfm_forecast_mode": tfm.forecast_mode if tfm else "average",
        "timesfm_horizon": tfm.horizon if tfm else 3,
        "timesfm_signal_threshold": tfm.signal_threshold if tfm else None,
        "timesfm_exit_signal_threshold": tfm.exit_signal_threshold if tfm else None,
        "timesfm_exit_threshold_mult": tfm.exit_threshold_mult if tfm else 0.85,
        "timesfm_timeframe_threshold_scale": tfm.timeframe_threshold_scale if tfm else True,
        "timesfm_predict_on_candle_close": tfm.predict_on_candle_close if tfm else True,
        "timesfm_fee_rate": tfm.fee_rate if tfm else 0.0004,
        "timesfm_slippage_rate": tfm.slippage_rate if tfm else 0.0005,
        "timesfm_safety_margin": tfm.safety_margin if tfm else 0.0001,
        "autopilot_enabled": ap.enabled,
        "autopilot_score_percentile": ap.score_percentile,
        "autopilot_score_k": ap.score_k,
        "autopilot_base_tp_atr_mult": ap.base_tp_atr_mult,
        "autopilot_base_sl_atr_mult": ap.base_sl_atr_mult,
        "autopilot_base_consecutive_required": ap.base_consecutive_required,
        "autopilot_atr_period": ap.atr_period,
        "autopilot_vol_lookback": ap.vol_lookback,
    }


def autopilot_config_from_engine(cfg: EngineConfig) -> AutopilotConfig:
    return cfg.autopilot
