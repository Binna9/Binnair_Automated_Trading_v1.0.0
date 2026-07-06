"""Autopilot 상태 JSON persist — API·재시작 복구용."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from binnair_trading_engine.autopilot.models import AutopilotState
from binnair_trading_engine.infra.timezone import now_kst

logger = logging.getLogger(__name__)


def resolve_autopilot_state_path(engine_state_path: Path | None) -> Path:
    """engine_state.json 과 같은 디렉터리에 autopilot_state.json."""
    if engine_state_path is not None:
        return engine_state_path.parent / "autopilot_state.json"
    return Path("data/state/autopilot_state.json")


class AutopilotStateStore:
    """Autopilot 진화 상태를 JSON 파일에 저장/복구."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AutopilotState | None:
        if not self._path.exists():
            return None
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            return AutopilotState(
                enabled=bool(data.get("enabled", False)),
                tick_count=int(data.get("tick_count", 0)),
                regime=str(data.get("regime", "unknown")),
                atr=float(data.get("atr", 0.0)),
                atr_pct=float(data.get("atr_pct", 0.0)),
                trend_slope=float(data.get("trend_slope", 0.0)),
                base_threshold=float(data.get("base_threshold", 0.0)),
                regime_threshold_mult=float(data.get("regime_threshold_mult", 1.0)),
                effective_threshold=float(data.get("effective_threshold", 0.0)),
                fee_floor=float(data.get("fee_floor", 0.0)),
                score_samples=int(data.get("score_samples", 0)),
                consecutive_required=int(data.get("consecutive_required", 2)),
                tp_pct=float(data.get("tp_pct", 0.0)),
                sl_pct=float(data.get("sl_pct", 0.0)),
                tp_atr_mult=float(data.get("tp_atr_mult", 0.0)),
                sl_atr_mult=float(data.get("sl_atr_mult", 0.0)),
                position_scale=float(data.get("position_scale", 1.0)),
                symbol=str(data.get("symbol", "")),
                run_id=str(data.get("run_id", "")),
                user_id=str(data.get("user_id", "default")),
                updated_at=str(data.get("updated_at", "")),
                extra=dict(data.get("extra") or {}),
            )
        except Exception as e:
            logger.warning("Autopilot state load failed: %s", e)
            return None

    def save(self, state: AutopilotState) -> None:
        state.updated_at = now_kst().isoformat()
        payload = asdict(state)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)


def load_autopilot_state_from_config(engine_state_path: Path | None) -> AutopilotState | None:
    """API 프로세스에서 설정 경로 기준으로 autopilot 상태 조회."""
    store = AutopilotStateStore(resolve_autopilot_state_path(engine_state_path))
    return store.load()
