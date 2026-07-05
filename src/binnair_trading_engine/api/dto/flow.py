"""
API 응답용 복합 DTO.

테이블 1개 = persistence/dto.py (EngineRunDTO, PositionSnapshotDTO 등)
화면 1장 = api/dto/flow.py (DashboardSummaryDTO, FlowTimelineItemDTO 등)

왜 필요: DB 테이블 DTO만으로는 "대시보드 요약", "타임라인 한 줄" 같은
여러 테이블을 묶은 응답 형태를 표현하기 어렵다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from binnair_trading_engine.infra.persistence.dto import (
    EngineRunDTO,
    OrderExecutionDTO,
    OrderRequestDTO,
    PositionSnapshotDTO,
)


@dataclass
class OrderFlowDTO:
    """order_request + 연결된 order_execution 묶음."""

    request: OrderRequestDTO
    executions: list[OrderExecutionDTO] = field(default_factory=list)


@dataclass
class FlowTimelineItemDTO:
    """매매 흐름 타임라인 1건."""

    event_type: str
    event_at: datetime
    run_id: str
    symbol: str | None
    summary: str
    correlation_id: str | None
    payload: dict[str, Any]


@dataclass
class DashboardSummaryDTO:
    """대시보드 요약."""

    user_id: str
    latest_run: EngineRunDTO | None
    open_positions: list[PositionSnapshotDTO]
    closed_positions_today: int
    realized_pnl_today: float
    recent_timeline: list[FlowTimelineItemDTO]
