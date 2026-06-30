"""
엔진 내부의 현재 포지션 상태를 관리한다.
포지션 오픈, 청산, 미실현 손익 갱신, DB snapshot 복구를 담당한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from binnair_trading_engine.domain.models import Position

if TYPE_CHECKING:
    pass


class PositionManager:
    """
    포지션 관리자.
    현재 보유 포지션 조회, 오픈, 청산, 미실현 손익 갱신.
    """

    def __init__(self, run_id: str = "") -> None:
        self._positions: dict[str, Position] = {}
        self._run_id = run_id

    def get_position(self, symbol: str) -> Position | None:
        """해당 심볼의 현재 포지션 반환. 없으면 None."""
        pos = self._positions.get(symbol)
        if pos is None or pos.is_closed():
            return None
        return pos

    def has_open_position(self, symbol: str) -> bool:
        """해당 심볼에 오픈 포지션이 있는지."""
        return self.get_position(symbol) is not None

    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        opened_at: datetime | None = None,
        tp_price: float | None = None,
        sl_price: float | None = None,
    ) -> Position:
        """
        신규 포지션 오픈.
        기존 오픈 포지션이 있으면 덮어쓴다.
        """
        now = datetime.utcnow()
        pos = Position(
            symbol=symbol,
            quantity=quantity,
            avg_entry_price=entry_price,
            side=side,
            tp_price=tp_price,
            sl_price=sl_price,
            status="OPEN",
            opened_at=opened_at if opened_at else now,
            closed_at=None,
            updated_at=now,
            run_id=self._run_id,
            unrealized_pnl=0.0,
        )
        self._positions[symbol] = pos
        return pos

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str = "",
        closed_at: datetime | None = None,
    ) -> Position | None:
        """
        포지션 청산.
        포지션이 없거나 이미 CLOSED면 None.
        exit_reason: TAKE_PROFIT | STOP_LOSS
        """
        pos = self._positions.get(symbol)
        if pos is None or pos.is_closed():
            return None

        now = datetime.utcnow()
        # LONG: realized_pnl = (exit - entry) * qty, SHORT: (entry - exit) * qty
        if pos.side == "LONG":
            realized_pnl = (exit_price - pos.avg_entry_price) * pos.quantity
        else:
            realized_pnl = (pos.avg_entry_price - exit_price) * pos.quantity

        closed_position = Position(
            symbol=pos.symbol,
            quantity=0.0,
            avg_entry_price=pos.avg_entry_price,
            side=pos.side,
            tp_price=pos.tp_price,
            sl_price=pos.sl_price,
            status="CLOSED",
            opened_at=pos.opened_at,
            closed_at=closed_at if closed_at else now,
            updated_at=now,
            run_id=pos.run_id,
            position_id=pos.position_id,
            unrealized_pnl=0.0,
            realized_pnl=realized_pnl,
            exit_reason=exit_reason,
            exit_price=exit_price,
        )
        del self._positions[symbol]
        return closed_position

    def update_unrealized_pnl(
        self,
        symbol: str,
        current_price: float,
    ) -> Position | None:
        """
        미실현 손익 갱신.
        LONG: (current - entry) * qty
        SHORT: (entry - current) * qty
        """
        pos = self.get_position(symbol)
        if pos is None:
            return None

        if pos.side == "LONG":
            pnl = (current_price - pos.avg_entry_price) * pos.quantity
        else:
            pnl = (pos.avg_entry_price - current_price) * pos.quantity

        updated = Position(
            symbol=pos.symbol,
            quantity=pos.quantity,
            avg_entry_price=pos.avg_entry_price,
            side=pos.side,
            tp_price=pos.tp_price,
            sl_price=pos.sl_price,
            status=pos.status,
            opened_at=pos.opened_at,
            closed_at=pos.closed_at,
            updated_at=datetime.utcnow(),
            run_id=pos.run_id,
            position_id=pos.position_id,
            unrealized_pnl=pnl,
        )
        self._positions[symbol] = updated
        return updated

    def list_open_positions(self) -> list[Position]:
        """현재 오픈된 포지션 목록 (스냅샷 반환)."""
        return [
            p for p in self._positions.values()
            if p.is_open()
        ]

    def restore_from_snapshot(self, snapshot: dict) -> Position | None:
        """
        DB position_snapshot에서 포지션 복구.
        status=OPEN, quantity>0인 경우만 복원.
        """
        status = snapshot.get("status") or "OPEN"
        quantity = float(snapshot.get("quantity") or 0)
        if status != "OPEN" or quantity <= 0:
            return None

        symbol = snapshot.get("symbol")
        if not symbol:
            return None

        side = (snapshot.get("side") or "LONG").upper()
        avg_entry_price = float(snapshot.get("avg_entry_price") or 0)
        tp_price = float(snapshot["tp_price"]) if snapshot.get("tp_price") is not None else None
        sl_price = float(snapshot["sl_price"]) if snapshot.get("sl_price") is not None else None
        opened_at = snapshot.get("opened_at")
        run_id = snapshot.get("run_id") or self._run_id

        if isinstance(opened_at, str):
            try:
                opened_at = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            except ValueError:
                opened_at = None
        if opened_at and getattr(opened_at, "tzinfo", None) is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)

        now = datetime.utcnow()
        pos = Position(
            symbol=symbol,
            quantity=quantity,
            avg_entry_price=avg_entry_price,
            side=side,
            tp_price=tp_price,
            sl_price=sl_price,
            status="OPEN",
            opened_at=opened_at if opened_at else now,
            closed_at=None,
            updated_at=now,
            run_id=run_id,
            unrealized_pnl=0.0,
        )
        self._positions[symbol] = pos
        return pos
