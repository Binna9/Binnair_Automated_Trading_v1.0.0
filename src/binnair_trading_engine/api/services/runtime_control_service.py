"""
UI 런타임 설정 저장·start/stop 명령 enqueue.
"""
from __future__ import annotations

import uuid
from typing import Any

from binnair_trading_engine.api.repositories.runtime_control_repository import (
    RuntimeControlRepository,
)
from binnair_trading_engine.config.runtime_config import (
    ADVANCED_PARAM_KEYS,
    BASIC_PARAM_KEYS,
    ENV_ONLY_KEYS,
    RUNTIME_PARAM_KEYS,
    RUNTIME_PARAM_SCHEMA,
    RuntimeConfigParams,
    merge_runtime_config,
    split_config_tiers,
)
from binnair_trading_engine.config.settings import EngineConfig
from binnair_trading_engine.infra.persistence.dto import (
    EngineCommandCreate,
    EngineRuntimeStateUpsert,
)


def _engine_run_status_hint(status: str | None, trading_enabled: bool | None) -> str:
    if status == "paused" or trading_enabled is False:
        return "매매 중지 (프로세스는 실행 중일 수 있음)"
    if status == "running" and trading_enabled:
        return "매매 활성"
    if status == "stopped":
        return "엔진 프로세스 종료"
    if status == "error":
        return "오류 종료"
    return "unknown"


def _config_response(cfg: EngineConfig, **extra: Any) -> dict[str, Any]:
    tiers = split_config_tiers(cfg)
    return {
        "config": tiers["full"],
        "config_basic": tiers["basic"],
        "config_advanced": tiers["advanced"],
        **extra,
    }


class RuntimeControlService:
    def __init__(self, repo: RuntimeControlRepository | None = None) -> None:
        self._repo = repo or RuntimeControlRepository()

    def get_schema(self) -> dict[str, Any]:
        return {
            "params": RUNTIME_PARAM_SCHEMA,
            "basic_keys": list(BASIC_PARAM_KEYS),
            "advanced_keys": list(ADVANCED_PARAM_KEYS),
            "env_only_keys": ENV_ONLY_KEYS,
        }

    def get_effective_config(self, base: EngineConfig, user_id: str = "default") -> dict[str, Any]:
        state = self._repo.get_state(user_id)
        patch = state.config_json if state else {}
        merged = merge_runtime_config(base, patch) if patch else base
        return _config_response(
            merged,
            config_version=state.config_version if state else 0,
            trading_enabled=state.trading_enabled if state else False,
            source="db" if state else "env_only",
        )

    def save_config(
        self,
        base: EngineConfig,
        params: RuntimeConfigParams,
        *,
        user_id: str = "default",
        trading_enabled: bool | None = None,
    ) -> dict[str, Any]:
        patch = params.to_patch_dict()
        state = self._repo.get_state(user_id)
        version = (state.config_version + 1) if state else 1
        prev = {
            k: v
            for k, v in (state.config_json if state else {}).items()
            if k in RUNTIME_PARAM_KEYS
        }
        merged_patch = {**prev, **patch}
        effective = merge_runtime_config(base, merged_patch)
        enabled = (
            trading_enabled
            if trading_enabled is not None
            else (state.trading_enabled if state else False)
        )
        saved = self._repo.upsert_state(
            EngineRuntimeStateUpsert(
                user_id=user_id,
                run_id=effective.run_context.run_id,
                strategy_id=effective.run_context.strategy_id,
                config_json=merged_patch,
                config_version=version,
                trading_enabled=enabled,
            )
        )
        return {
            **_config_response(
                effective,
                config_version=saved.config_version,
                trading_enabled=saved.trading_enabled,
            ),
            "merged_patch": merged_patch,
        }

    def start(
        self,
        base: EngineConfig,
        params: RuntimeConfigParams,
        *,
        user_id: str = "default",
    ) -> dict[str, Any]:
        saved = self.save_config(
            base, params, user_id=user_id, trading_enabled=True
        )
        corr = str(uuid.uuid4())
        cmd_id = self._repo.enqueue_command(
            EngineCommandCreate(
                user_id=user_id,
                action="start",
                config_json=saved["merged_patch"],
                config_version=saved["config_version"],
                correlation_id=corr,
            )
        )
        out = {k: v for k, v in saved.items() if k != "merged_patch"}
        self._repo.set_engine_run_trading_active(
            saved["config"].get("run_id") or base.run_context.run_id,
            active=True,
            user_id=user_id,
        )
        return {**out, "command_id": cmd_id, "correlation_id": corr, "action": "start"}

    def stop(self, *, user_id: str = "default") -> dict[str, Any]:
        state = self._repo.get_state(user_id)
        corr = str(uuid.uuid4())
        cmd_id = self._repo.enqueue_command(
            EngineCommandCreate(
                user_id=user_id,
                action="stop",
                config_json=state.config_json if state else None,
                config_version=state.config_version if state else None,
                correlation_id=corr,
            )
        )
        if state:
            self._repo.upsert_state(
                EngineRuntimeStateUpsert(
                    user_id=user_id,
                    run_id=state.run_id,
                    strategy_id=state.strategy_id,
                    config_json=state.config_json,
                    config_version=state.config_version,
                    trading_enabled=False,
                )
            )
            self._repo.set_engine_run_trading_active(
                state.run_id, active=False, user_id=user_id
            )
        return {
            "command_id": cmd_id,
            "correlation_id": corr,
            "action": "stop",
            "trading_enabled": False,
        }

    def get_status(self, base: EngineConfig, user_id: str = "default") -> dict[str, Any]:
        state = self._repo.get_state(user_id)
        effective = self.get_effective_config(base, user_id)
        run_id = base.run_context.run_id
        if state and state.run_id:
            run_id = state.run_id
        engine_run = self._repo.get_engine_run_status(run_id, user_id)
        commands = self._repo.list_recent_commands(user_id, limit=5)
        return {
            **effective,
            "engine_run": {
                "run_id": run_id,
                "status": engine_run.get("status") if engine_run else None,
                "started_at": engine_run.get("started_at") if engine_run else None,
                "strategy_id": engine_run.get("strategy_id") if engine_run else None,
                "status_meaning": _engine_run_status_hint(
                    engine_run.get("status") if engine_run else None,
                    effective.get("trading_enabled"),
                ),
            },
            "recent_commands": [
                {
                    "id": c.id,
                    "action": c.action,
                    "status": c.status,
                    "correlation_id": c.correlation_id,
                    "error_message": c.error_message,
                    "created_at": c.created_at,
                    "processed_at": c.processed_at,
                }
                for c in commands
            ],
        }
