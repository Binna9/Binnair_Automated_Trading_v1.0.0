"""predictor identity defaults align run_id/model with predictor_type."""

from binnair_trading_engine.config.runtime_config import apply_predictor_identity_defaults


def test_fincast_identity_overwrites_timesfm_labels() -> None:
    out = apply_predictor_identity_defaults(
        {
            "predictor_type": "fincast",
            "run_id": "prod_timesfm_run",
            "strategy_id": "timesfm_consecutive_long_short",
            "model_version": "timesfm-2.5-200m",
            "symbol": "XRPUSDT",
        }
    )
    assert out["run_id"] == "prod_fincast_run"
    assert out["strategy_id"] == "fincast_passthrough"
    assert out["model_version"] == "fincast-1b"
    assert out["feature_set_version"] == "price-history-v1"
    assert out["symbol"] == "XRPUSDT"


def test_timesfm_identity() -> None:
    out = apply_predictor_identity_defaults({"predictor_type": "timesfm"})
    assert out["run_id"] == "prod_timesfm_run"
    assert out["model_version"] == "timesfm-2.5-200m"


def test_no_predictor_type_unchanged() -> None:
    patch = {"run_id": "custom", "symbol": "BTCUSDT"}
    assert apply_predictor_identity_defaults(patch) == patch
