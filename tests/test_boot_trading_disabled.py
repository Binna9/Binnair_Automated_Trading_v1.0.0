"""Boot must force trading off even if DB had trading_enabled=true."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from binnair_trading_engine.engine.runtime_control import RuntimeControlPoller
from binnair_trading_engine.infra.persistence.dto import EngineRuntimeStateDTO


def _engine_mock() -> MagicMock:
    engine = MagicMock()
    engine._ctx = SimpleNamespace(
        run_id="run1",
        strategy_id="s1",
        model_version="m1",
        feature_set_version="f1",
        version="1.0.0",
        user_id="default",
    )
    engine._config.exchange.paper_mode = True
    engine._build_config_snapshot.return_value = {"symbol": "XRPUSDT"}
    return engine


def test_sync_on_startup_forces_trading_off() -> None:
    engine = _engine_mock()
    poller = RuntimeControlPoller(engine, user_id="default")
    poller._repos = MagicMock()
    poller._repos.engine_run = MagicMock()
    poller._repos.engine_runtime_state = MagicMock()
    poller._repos.engine_command.claim_pending.return_value = None

    state = EngineRuntimeStateDTO(
        user_id="default",
        run_id="run1",
        strategy_id="s1",
        config_json={"symbol": "XRPUSDT"},
        config_version=3,
        trading_enabled=True,
    )

    with patch(
        "binnair_trading_engine.engine.runtime_control.load_runtime_state",
        return_value=state,
    ):
        poller.sync_on_startup()

    engine.apply_runtime_config.assert_called_once_with({"symbol": "XRPUSDT"})
    engine.set_trading_enabled.assert_called_with(False)
    upsert = poller._repos.engine_runtime_state.upsert
    upsert.assert_called_once()
    assert upsert.call_args.args[0].trading_enabled is False
    engine._storage.record_engine_start.assert_called()
    assert (
        engine._storage.record_engine_start.call_args.kwargs["trading_enabled"]
        is False
    )
    poller._repos.engine_command.claim_pending.assert_called()


def test_sync_on_startup_applies_pending_start_after_force_off() -> None:
    engine = _engine_mock()
    poller = RuntimeControlPoller(engine, user_id="default")
    poller._repos = MagicMock()
    poller._repos.engine_run = MagicMock()
    poller._repos.engine_runtime_state = MagicMock()

    start_cmd = SimpleNamespace(
        id=9,
        action="start",
        config_json={"symbol": "XRPUSDT"},
        config_version=4,
        correlation_id="c1",
    )
    poller._repos.engine_command.claim_pending.side_effect = [start_cmd, None]

    state = EngineRuntimeStateDTO(
        user_id="default",
        run_id="run1",
        strategy_id="s1",
        config_json={"symbol": "XRPUSDT"},
        config_version=3,
        trading_enabled=False,
    )

    with patch(
        "binnair_trading_engine.engine.runtime_control.load_runtime_state",
        return_value=state,
    ):
        poller.sync_on_startup()

    assert engine.set_trading_enabled.call_args_list[-1].args[0] is True
    calls = engine._storage.record_engine_start.call_args_list
    assert calls[-1].kwargs["trading_enabled"] is True
    poller._repos.engine_command.mark_done.assert_called_with(9)
