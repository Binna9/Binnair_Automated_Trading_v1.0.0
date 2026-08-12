"""UI runtime: predictor_type 선택 + 모델별 patch 매핑."""

from __future__ import annotations

from binnair_trading_engine.config.runtime_config import (
    BASIC_PARAM_KEYS,
    PARAM_GROUPS,
    RUNTIME_PARAM_SCHEMA,
    engine_config_to_runtime_params,
    runtime_patch_to_nested,
)
from binnair_trading_engine.config.settings import (
    EngineConfig,
    ExchangeConfig,
    MarketDataConfig,
    PredictorFinCastConfig,
    PredictorTimesFMConfig,
    RunContext,
    StorageConfig,
)


def _base_cfg() -> EngineConfig:
    return EngineConfig(
        run_context=RunContext(
            run_id="t",
            strategy_id="s",
            model_version="v",
            feature_set_version="f",
        ),
        exchange=ExchangeConfig(),
        storage=StorageConfig(),
        market_data=MarketDataConfig(symbol="BTCUSDT"),
        predictor_type="timesfm",
        predictor_timesfm_config=PredictorTimesFMConfig(timeframe="1m"),
        predictor_fincast_config=PredictorFinCastConfig(
            timeframe="5m",
            checkpoint_path="/tmp/f.pth",
            repo_path="/tmp/src",
        ),
    )


def test_predictor_type_in_basic_keys() -> None:
    assert "predictor_type" in BASIC_PARAM_KEYS
    assert "fincast_timeframe" in BASIC_PARAM_KEYS


def test_schema_visible_when_for_model_groups() -> None:
    by_key = {e["key"]: e for e in RUNTIME_PARAM_SCHEMA}
    assert by_key["predictor_type"]["options"] == ["timesfm", "fincast"]
    assert by_key["timesfm_timeframe"]["visible_when"] == {
        "predictor_type": "timesfm"
    }
    assert by_key["fincast_checkpoint_path"]["visible_when"] == {
        "predictor_type": "fincast"
    }
    groups = {g["id"]: g for g in PARAM_GROUPS}
    assert groups["fincast"]["visible_when"]["predictor_type"] == "fincast"


def test_runtime_patch_maps_fincast_and_predictor_type() -> None:
    nested = runtime_patch_to_nested(
        {
            "predictor_type": "fincast",
            "fincast_timeframe": "5m",
            "fincast_checkpoint_path": "/models/f.pth",
            "fincast_repo_path": "/opt/FinCast-fts/src",
        }
    )
    assert nested["predictor_type"] == "fincast"
    assert nested["predictor_config"]["fincast"]["timeframe"] == "5m"
    assert nested["predictor_config"]["fincast"]["checkpoint_path"] == "/models/f.pth"


def test_runtime_params_export_both_model_dirs() -> None:
    params = engine_config_to_runtime_params(_base_cfg())
    assert params["predictor_type"] == "timesfm"
    assert params["timesfm_timeframe"] == "1m"
    assert params["fincast_timeframe"] == "5m"
    assert params["fincast_checkpoint_path"] == "/tmp/f.pth"
