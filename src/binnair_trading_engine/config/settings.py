"""
엔진 설정 구조.
Paper trading 기본, 환경변수/파일 기반 로딩.
"""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class ExchangeConfig:
    """거래소 설정."""
    adapter_type: str = "binance"
    paper_mode: bool = True
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""


@dataclass
class StorageConfig:
    """스토리지(Postgres) 설정."""
    host: str = "localhost"
    port: int = 5432
    dbname: str = "binnair_engine"
    user: str = "postgres"
    password: str = ""
    schema: str = "trade"

    def to_database_url(self) -> str:
        """PostgreSQL 연결 URL 생성 (psycopg3 드라이버)."""
        from urllib.parse import quote_plus
        return (
            f"postgresql+psycopg://{self.user}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )


@dataclass
class PredictorTorchConfig:
    """TorchPredictor 아티팩트 설정."""
    model_path: str = ""
    scaler_path: str = ""
    feature_order_path: str = ""
    model_version: str = ""
    feature_set_version: str = ""
    scaler_version: str = ""


@dataclass
class EngineConfig:
    """엔진 전체 설정."""
    run_context: RunContext
    exchange: ExchangeConfig
    storage: StorageConfig
    predictor_type: str = "dummy"
    predictor_config: PredictorTorchConfig | None = None
    risk_enabled: bool = True
    state_persist_path: Path | None = None
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineConfig":
        """dict에서 설정 로드."""
        run = data.get("run_context", {})
        run_ctx = RunContext(
            run_id=run.get("run_id", "default_run"),
            strategy_id=run.get("strategy_id", "default_strategy"),
            model_version=run.get("model_version", "v1"),
            feature_set_version=run.get("feature_set_version", "v1"),
            version=run.get("version", "1.0.0"),
        )
        exc = data.get("exchange", {})
        exc_cfg = ExchangeConfig(
            adapter_type=exc.get("adapter_type", "binance"),
            paper_mode=exc.get("paper_mode", True),
            api_key=exc.get("api_key", ""),
            api_secret=exc.get("api_secret", ""),
            base_url=exc.get("base_url", ""),
        )
        stor = data.get("storage", {})
        stor_cfg = StorageConfig(
            host=stor.get("host", "localhost"),
            port=int(stor.get("port", 5432)),
            dbname=stor.get("dbname", "binnair_engine"),
            user=stor.get("user", "postgres"),
            password=stor.get("password", ""),
            schema=stor.get("schema", "trade"),
        )
        pc = data.get("predictor_config") or {}
        tor = pc.get("torch") or {}
        pred_torch = PredictorTorchConfig(
            model_path=tor.get("model_path", ""),
            scaler_path=tor.get("scaler_path", ""),
            feature_order_path=tor.get("feature_order_path", ""),
            model_version=tor.get("model_version", ""),
            feature_set_version=tor.get("feature_set_version", ""),
            scaler_version=tor.get("scaler_version", ""),
        ) if tor else None
        sp = data.get("state_persist_path")
        return cls(
            run_context=run_ctx,
            exchange=exc_cfg,
            storage=stor_cfg,
            predictor_type=data.get("predictor_type", "dummy"),
            predictor_config=pred_torch,
            risk_enabled=data.get("risk_enabled", True),
            state_persist_path=Path(sp) if sp else None,
            log_level=data.get("log_level", "INFO"),
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
