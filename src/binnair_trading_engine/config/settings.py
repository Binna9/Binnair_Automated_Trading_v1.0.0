"""
엔진 설정 구조와 기본값을 정의한다.
YAML/환경변수에서 읽은 값을 RunContext, Exchange, Storage, Sizing, Risk 설정으로 변환한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RunContext:
    """실행 추적용 컨텍스트."""
    run_id: str
    strategy_id: str
    model_version: str
    feature_set_version: str
    version: str = "1.0.0"
    user_id: str = "default"  # 사용자별 이력 분리 (UUID 등 VARCHAR 36)


@dataclass
class ExchangeConfig:
    """거래소 설정."""
    adapter_type: str = "binance"  # 거래소 어댑터 타입. 현재 구현은 binance 전용.
    market_type: str = "futures"  # 시장 타입: "spot"(현물) | "futures"(선물 USD-M).
    paper_mode: bool = True  # True=로컬 모의거래, False=거래소 API(실거래/테스트넷) 사용.
    api_key: str = "xlgGWr2oz7HVDC3HIEc215eh6FL5yMc5zKT8DjQgFTUJKslnx5q0rG7u0YjHYsXj"  # 테스트넷/실거래 API Key.
    api_secret: str = "WUKjcGfFbe7B4uL2CevElu8UGMrPjyugQuvEfZAlN6Zh86n36TUYMQ1kNB5DOKVu"  # 테스트넷/실거래 API Secret.
    base_url: str = "https://testnet.binancefuture.com"  # Binance Futures Testnet URL.
    leverage: int = 3  # 선물 레버리지 배수. market_type="futures"에서만 적용.
    margin_type: str = "ISOLATED"  # 선물 마진 모드: "ISOLATED"(격리) | "CROSSED"(교차).
    position_side_mode: str = "ONE_WAY"  # 포지션 모드: "ONE_WAY"(단방향) | "HEDGE"(양방향).
    oco_enabled: bool = False  # 진입 직후 TP/SL 보호주문(OCO 유사 reduceOnly 2주문) 자동 등록 여부.


@dataclass
class StorageConfig:
    """스토리지(Postgres) 설정."""
    backend: str = "postgres"  # "memory"(파이썬 메모리) | "postgres"
    host: str = "localhost"
    port: int = 5432
    dbname: str = "binnair"
    user: str = "binnair"
    password: str = "hun380638@@"
    schema: str = "trade"

    def to_database_url(self) -> str:
        """PostgreSQL 연결 URL 생성 (psycopg3 드라이버)."""
        from urllib.parse import quote_plus
        return (
            f"postgresql+psycopg://{self.user}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )


@dataclass
class MarketDataConfig:
    """시세 수신 설정."""
    enabled: bool = True
    provider: str = "binance_rest"
    symbol: str = "BTCUSDT"
    poll_interval_seconds: float = 5.0
    base_url: str = "https://api.binance.com"
    timeout: float = 10.0


@dataclass
class TradeRulesConfig:
    """진입/청산 규칙 (TP/SL 등)."""

    tp_pct: float = 0.0  # TP: 목표가 = 체결가 * (1 + tp_pct)
    sl_pct: float = 0.0  # SL: 손절가 = 체결가 * (1 - sl_pct)


@dataclass
class SizingConfig:
    """지갑 잔고 기반 주문 수량 계산 설정."""

    quote_asset: str = "USDT"  # 주문 금액 기준 자산. Binance USD-M Futures는 보통 USDT.
    risk_per_trade_pct: float = 0.005  # 1회 거래에서 감수할 최대 손실 비율. 0.005 = 지갑의 0.5%.
    max_position_notional_pct: float = 0.20  # 한 포지션의 최대 명목 금액 비율. 0.20 = 지갑의 20%.
    min_order_notional_usdt: float = 5.0  # 이 금액보다 작은 주문은 거래소 최소 주문금액 미달 가능성이 있어 차단.
    max_leverage: int = 2  # sizing 계산상 허용할 최대 레버리지 상한. 거래소 leverage 설정과 함께 관리.
    fallback_equity_usdt: float = 0.0  # 잔고 조회 실패 시 사용할 비상 값. 0이면 주문 생성 안 함.


@dataclass
class RiskConfig:
    """주문 직전 최종 리스크 제한 설정."""

    max_position_notional_pct: float = 0.20  # 지갑 대비 최대 포지션 명목 금액 비율.
    daily_loss_limit_pct: float = 0.03  # 하루 손실 제한. 0.03 = 지갑의 3% 손실 시 신규 주문 차단.
    duplicate_order_window_seconds: int = 180  # 동일 심볼/동일 방향 중복 주문 최소 간격.


@dataclass
class SignalPolicyConfig:
    """모델 시그널 후처리 정책 설정."""

    consecutive_required: int = 3
    mode: str = "long_only"


@dataclass
class PredictorTimesFMConfig:
    """TimesFM 사전학습 모델 예측기 설정."""
    model_id: str = "google/timesfm-2.5-200m-pytorch"
    context_length: int = 128
    min_context: int = 64
    horizon: int = 3
    forecast_index: int = -1
    use_ohlcv_history: bool = True
    timeframe: str = "1m"
    fee_rate: float = 0.0004
    slippage_rate: float = 0.0005
    safety_margin: float = 0.001
    model_version: str = "timesfm-2.5-200m"
    feature_set_version: str = "price-history-v1"


@dataclass
class ApiConfig:
    """조회 API(FastAPI) 서버 설정."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class EngineConfig:
    """엔진 전체 설정."""
    run_context: RunContext
    exchange: ExchangeConfig
    storage: StorageConfig
    market_data: MarketDataConfig
    trade_rules: TradeRulesConfig = field(default_factory=TradeRulesConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    signal_policy: SignalPolicyConfig = field(default_factory=SignalPolicyConfig)
    predictor_type: str = "timesfm"
    predictor_timesfm_config: PredictorTimesFMConfig | None = None
    risk_enabled: bool = True
    state_persist_path: Path | None = None
    log_level: str = "INFO"
    persist_model_inference: bool = False  # BUY/SELL 시에만 model_inference_event 저장
    flatten_on_shutdown: bool = True  # graceful 종료 시 열린 포지션 시장가 청산
    api: ApiConfig = field(default_factory=ApiConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineConfig":
        """dict에서 설정 로드."""
        run = data.get("run_context", {})
        default_run = RunContext(
            run_id="default_run",
            strategy_id="default_strategy",
            model_version="v1",
            feature_set_version="v1",
        )
        run_ctx = RunContext(
            run_id=run.get("run_id", default_run.run_id),
            strategy_id=run.get("strategy_id", default_run.strategy_id),
            model_version=run.get("model_version", default_run.model_version),
            feature_set_version=run.get("feature_set_version", default_run.feature_set_version),
            version=run.get("version", default_run.version),
            user_id=run.get("user_id", default_run.user_id),
        )
        exc = data.get("exchange", {})
        default_exchange = ExchangeConfig()
        exc_cfg = ExchangeConfig(
            adapter_type=exc.get("adapter_type", default_exchange.adapter_type),
            market_type=exc.get("market_type", default_exchange.market_type),
            paper_mode=exc.get("paper_mode", default_exchange.paper_mode),
            api_key=exc.get("api_key", default_exchange.api_key),
            api_secret=exc.get("api_secret", default_exchange.api_secret),
            base_url=exc.get("base_url", default_exchange.base_url),
            leverage=int(exc.get("leverage", default_exchange.leverage)),
            margin_type=exc.get("margin_type", default_exchange.margin_type),
            position_side_mode=exc.get("position_side_mode", default_exchange.position_side_mode),
            oco_enabled=exc.get("oco_enabled", default_exchange.oco_enabled),
        )
        stor = data.get("storage", {})
        md = data.get("market_data", {})
        default_market_data = MarketDataConfig()
        md_cfg = MarketDataConfig(
            enabled=md.get("enabled", default_market_data.enabled),
            provider=md.get("provider", default_market_data.provider),
            symbol=md.get("symbol", default_market_data.symbol),
            poll_interval_seconds=float(md.get("poll_interval_seconds", default_market_data.poll_interval_seconds)),
            base_url=md.get("base_url", default_market_data.base_url),
            timeout=float(md.get("timeout", default_market_data.timeout)),
        )
        default_storage = StorageConfig()
        stor_cfg = StorageConfig(
            backend=stor.get("backend", default_storage.backend),
            host=stor.get("host", default_storage.host),
            port=int(stor.get("port", default_storage.port)),
            dbname=stor.get("dbname", default_storage.dbname),
            user=stor.get("user", default_storage.user),
            password=stor.get("password", default_storage.password),
            schema=stor.get("schema", default_storage.schema),
        )
        tr = data.get("trade_rules", {})
        default_trade_rules = TradeRulesConfig()
        trade_rules_cfg = TradeRulesConfig(
            tp_pct=float(tr.get("tp_pct", default_trade_rules.tp_pct)),
            sl_pct=float(tr.get("sl_pct", default_trade_rules.sl_pct)),
        )
        sizing = data.get("sizing", {})
        default_sizing = SizingConfig()
        sizing_cfg = SizingConfig(
            quote_asset=sizing.get("quote_asset", default_sizing.quote_asset),
            risk_per_trade_pct=float(
                sizing.get("risk_per_trade_pct", default_sizing.risk_per_trade_pct)
            ),
            max_position_notional_pct=float(
                sizing.get(
                    "max_position_notional_pct",
                    default_sizing.max_position_notional_pct,
                )
            ),
            min_order_notional_usdt=float(
                sizing.get(
                    "min_order_notional_usdt",
                    default_sizing.min_order_notional_usdt,
                )
            ),
            max_leverage=int(sizing.get("max_leverage", default_sizing.max_leverage)),
            fallback_equity_usdt=float(
                sizing.get("fallback_equity_usdt", default_sizing.fallback_equity_usdt)
            ),
        )
        risk = data.get("risk", {})
        default_risk = RiskConfig()
        risk_cfg = RiskConfig(
            max_position_notional_pct=float(
                risk.get(
                    "max_position_notional_pct",
                    default_risk.max_position_notional_pct,
                )
            ),
            daily_loss_limit_pct=float(
                risk.get("daily_loss_limit_pct", default_risk.daily_loss_limit_pct)
            ),
            duplicate_order_window_seconds=int(
                risk.get(
                    "duplicate_order_window_seconds",
                    default_risk.duplicate_order_window_seconds,
                )
            ),
        )
        sp_cfg_data = data.get("signal_policy", {})
        default_signal_policy = SignalPolicyConfig()
        signal_policy_cfg = SignalPolicyConfig(
            consecutive_required=int(
                sp_cfg_data.get(
                    "consecutive_required",
                    default_signal_policy.consecutive_required,
                )
            ),
            mode=sp_cfg_data.get("mode", default_signal_policy.mode),
        )
        pc = data.get("predictor_config") or {}
        tfm = pc.get("timesfm") or {}
        pred_timesfm = PredictorTimesFMConfig(
            model_id=tfm.get("model_id", PredictorTimesFMConfig.model_id),
            context_length=int(tfm.get("context_length", PredictorTimesFMConfig.context_length)),
            min_context=int(tfm.get("min_context", PredictorTimesFMConfig.min_context)),
            horizon=int(tfm.get("horizon", PredictorTimesFMConfig.horizon)),
            forecast_index=int(tfm.get("forecast_index", PredictorTimesFMConfig.forecast_index)),
            use_ohlcv_history=bool(tfm.get("use_ohlcv_history", PredictorTimesFMConfig.use_ohlcv_history)),
            timeframe=tfm.get("timeframe", PredictorTimesFMConfig.timeframe),
            fee_rate=float(tfm.get("fee_rate", PredictorTimesFMConfig.fee_rate)),
            slippage_rate=float(tfm.get("slippage_rate", PredictorTimesFMConfig.slippage_rate)),
            safety_margin=float(tfm.get("safety_margin", PredictorTimesFMConfig.safety_margin)),
            model_version=tfm.get("model_version", PredictorTimesFMConfig.model_version),
            feature_set_version=tfm.get("feature_set_version", PredictorTimesFMConfig.feature_set_version),
        ) if tfm else None
        sp = data.get("state_persist_path")
        api = data.get("api", {})
        default_api = ApiConfig()
        cors = api.get("cors_origins", default_api.cors_origins)
        if isinstance(cors, str):
            cors = [cors]
        api_cfg = ApiConfig(
            enabled=bool(api.get("enabled", default_api.enabled)),
            host=api.get("host", default_api.host),
            port=int(api.get("port", default_api.port)),
            cors_origins=list(cors) if cors else default_api.cors_origins,
        )
        return cls(
            run_context=run_ctx,
            exchange=exc_cfg,
            storage=stor_cfg,
            market_data=md_cfg,
            trade_rules=trade_rules_cfg,
            sizing=sizing_cfg,
            risk=risk_cfg,
            signal_policy=signal_policy_cfg,
            predictor_type=data.get("predictor_type", "timesfm"),
            predictor_timesfm_config=pred_timesfm,
            risk_enabled=data.get("risk_enabled", True),
            state_persist_path=Path(sp) if sp else None,
            log_level=data.get("log_level", "INFO"),
            persist_model_inference=data.get("persist_model_inference", False),
            flatten_on_shutdown=bool(data.get("flatten_on_shutdown", True)),
            api=api_cfg,
        )


def load_config(config_path: Path | str | None = None) -> EngineConfig:
    """
    설정 로드. 경로 미지정 시 기본값 반환.
    환경변수 CONFIG_PATH 사용 가능.
    """
    import os
    path = config_path or os.environ.get("CONFIG_PATH")
    if path:
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return EngineConfig.from_dict(data)
    return EngineConfig.from_dict({})
