"""
UI start/stop 명령 poll 및 런타임 설정 적용.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from binnair_trading_engine.config.runtime_config import engine_config_to_runtime_params
from binnair_trading_engine.config.runtime_loader import load_runtime_state
from binnair_trading_engine.infra.persistence.repositories.postgres import (
    PostgresRepositoryFactory,
)

if TYPE_CHECKING:
    from binnair_trading_engine.engine.core import TradingEngine

logger = logging.getLogger(__name__)


class RuntimeControlPoller:
    """엔진 메인 루프에서 주기적으로 DB 명령·설정을 동기화."""

    def __init__(self, engine: TradingEngine, user_id: str = "default") -> None:
        self._engine = engine
        self._user_id = user_id
        self._repos = PostgresRepositoryFactory()
        self._last_config_version: int | None = None

    def sync_on_startup(self) -> None:
        """기동 시 DB runtime state 반영."""
        state = load_runtime_state(self._user_id)
        if state is None:
            self._engine.set_trading_enabled(False)
            self._sync_engine_run_trading_status(False)
            logger.info(
                "No runtime state in DB — trading disabled until UI start"
            )
            return
        self._last_config_version = state.config_version
        if state.config_json:
            self._engine.apply_runtime_config(state.config_json)
        self._engine.set_trading_enabled(state.trading_enabled)
        self._sync_engine_run_trading_status(state.trading_enabled, state.run_id)
        logger.info(
            "Runtime state loaded: trading_enabled=%s config_version=%s",
            state.trading_enabled,
            state.config_version,
        )

    def _sync_engine_run_trading_status(
        self, trading_enabled: bool, run_id: str | None = None
    ) -> None:
        rid = run_id or self._engine._ctx.run_id
        status = "running" if trading_enabled else "paused"
        try:
            self._repos.engine_run.update_status(
                rid, status, user_id=self._user_id
            )
        except Exception:
            logger.exception("engine_run status sync failed run_id=%s", rid)

    def poll(self) -> None:
        """pending command 처리 + config_version 변경 동기화."""
        self._process_commands()
        self._sync_config_version()

    def _process_commands(self) -> None:
        while True:
            cmd = self._repos.engine_command.claim_pending(self._user_id)
            if cmd is None:
                break
            try:
                if cmd.action == "start":
                    if cmd.config_json:
                        self._engine.apply_runtime_config(cmd.config_json)
                    self._engine.set_trading_enabled(True)
                    if cmd.config_version is not None:
                        self._last_config_version = cmd.config_version
                    self._sync_engine_run_trading_status(True)
                    logger.info(
                        "Runtime command start applied (id=%s corr=%s)",
                        cmd.id,
                        cmd.correlation_id,
                    )
                elif cmd.action == "stop":
                    self._engine.set_trading_enabled(False)
                    self._sync_engine_run_trading_status(False)
                    logger.info(
                        "Runtime command stop applied (id=%s corr=%s)",
                        cmd.id,
                        cmd.correlation_id,
                    )
                else:
                    raise ValueError(f"unknown action: {cmd.action}")
                self._repos.engine_command.mark_done(cmd.id)
            except Exception as e:
                logger.exception("Runtime command failed id=%s", cmd.id)
                self._repos.engine_command.mark_done(cmd.id, error_message=str(e))

    def _sync_config_version(self) -> None:
        state = load_runtime_state(self._user_id)
        if state is None:
            return
        if (
            self._last_config_version is not None
            and state.config_version == self._last_config_version
        ):
            return
        if state.config_json:
            self._engine.apply_runtime_config(state.config_json)
        self._engine.set_trading_enabled(state.trading_enabled)
        self._last_config_version = state.config_version
        self._sync_engine_run_trading_status(state.trading_enabled, state.run_id)
        logger.info(
            "Runtime config synced: version=%s trading_enabled=%s",
            state.config_version,
            state.trading_enabled,
        )


def build_config_snapshot(engine: TradingEngine) -> dict:
    """engine_run.config_snapshot용 flat runtime dict."""
    return engine_config_to_runtime_params(engine.config)
