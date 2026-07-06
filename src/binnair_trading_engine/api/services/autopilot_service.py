"""Autopilot 상태 조회 (JSON persist 파일)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from binnair_trading_engine.autopilot.persist import (
    load_autopilot_state_from_config,
    resolve_autopilot_state_path,
)
from binnair_trading_engine.config.settings import EngineConfig


def get_autopilot_status(
    cfg: EngineConfig,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_path = resolve_autopilot_state_path(cfg.state_persist_path)
    state = load_autopilot_state_from_config(cfg.state_persist_path)

    if state is None:
        return {
            "enabled": cfg.autopilot.enabled,
            "available": False,
            "state_path": str(state_path),
            "message": "Autopilot state file not found (engine may not have ticked yet).",
        }

    if run_id and state.run_id and state.run_id != run_id:
        return {
            "enabled": state.enabled,
            "available": False,
            "state_path": str(state_path),
            "message": f"Stored run_id={state.run_id!r} does not match requested {run_id!r}.",
            "stored_run_id": state.run_id,
        }

    payload = asdict(state)
    payload["state_path"] = str(state_path)
    payload["available"] = True
    return payload
