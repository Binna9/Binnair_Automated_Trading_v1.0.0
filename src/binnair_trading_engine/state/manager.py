"""
엔진 실행 상태를 메모리와 선택적 파일에 저장한다.
start, heartbeat, stop 상태를 기록해 장애 복구 기반을 제공한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import EngineContext, Order, OrderIntent


class EnginePhase(str, Enum):
    """엔진 실행 단계."""

    INIT = "init"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class EngineState:
    """엔진 현재 상태 스냅샷."""

    run_id: str
    phase: EnginePhase
    strategy_id: str
    model_version: str
    feature_set_version: str
    last_heartbeat_at: datetime | None
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "strategy_id": self.strategy_id,
            "model_version": self.model_version,
            "feature_set_version": self.feature_set_version,
            "last_heartbeat_at": (
                self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None
            ),
            "updated_at": self.updated_at.isoformat(),
        }


class StateManager:
    """엔진 상태 저장/복구 및 일관성 보장. 메모리 + 선택적 파일 persist."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._persist_path = persist_path
        self._state: EngineState | None = None

    def start(self, ctx: "EngineContext") -> None:
        """엔진 시작: 복구 시도 후 RUNNING으로 전환."""
        if self._persist_path and self._persist_path.exists():
            loaded = self._load()
            if loaded and loaded.run_id == ctx.run_id:
                self._state = loaded
                self._state.phase = EnginePhase.RUNNING  # type: ignore
        if self._state is None:
            self._state = EngineState(
                run_id=ctx.run_id,
                phase=EnginePhase.RUNNING,
                strategy_id=ctx.strategy_id,
                model_version=ctx.model_version,
                feature_set_version=ctx.feature_set_version,
                last_heartbeat_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        self._save()

    def stop(self) -> None:
        """엔진 종료."""
        if self._state:
            self._state.phase = EnginePhase.STOPPED  # type: ignore
            self._state.updated_at = datetime.utcnow()
            self._save()

    def heartbeat(self) -> None:
        """주기적 heartbeat."""
        if self._state:
            self._state.last_heartbeat_at = datetime.utcnow()
            self._state.updated_at = datetime.utcnow()
            self._save()

    def update_position(self, intent: "OrderIntent", order: "Order") -> None:
        """포지션 변경 시 호출. 추후 스토리지 연동."""
        self.heartbeat()

    def _save(self) -> None:
        if self._persist_path and self._state:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, indent=2)

    def _load(self) -> EngineState | None:
        if not self._persist_path or not self._persist_path.exists():
            return None
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
            return EngineState(
                run_id=data["run_id"],
                phase=EnginePhase(data["phase"]),
                strategy_id=data["strategy_id"],
                model_version=data["model_version"],
                feature_set_version=data["feature_set_version"],
                last_heartbeat_at=(
                    datetime.fromisoformat(data["last_heartbeat_at"])
                    if data.get("last_heartbeat_at")
                    else None
                ),
                updated_at=datetime.fromisoformat(data["updated_at"]),
            )
        except Exception:
            return None
