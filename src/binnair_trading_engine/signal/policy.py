"""
모델 시그널을 주문 가능한 정책 신호로 필터링한다.
심볼별 최근 N개 BUY/HOLD/SELL 연속성을 기준으로 진입과 청산을 허용한다.
"""
from __future__ import annotations

from collections import defaultdict, deque

from binnair_trading_engine.domain.models import SignalAction


class ConsecutiveSignalPolicy:
    """
    심볼별 최근 N개 시그널이 같은 방향일 때만 통과시키는 정책.

    long_only:
    - BUY N회 연속: 신규 롱 진입
    - SELL N회 연속: 보유 롱 청산
    - HOLD: 포지션 유지

    long_short (선물 ONE_WAY 권장):
    - BUY N회 연속: 롱 진입 또는 숏 청산
    - SELL N회 연속: 숏 진입 또는 롱 청산
    """

    def __init__(
        self,
        consecutive_required: int = 3,
        mode: str = "long_only",
    ) -> None:
        self._required = max(1, int(consecutive_required))
        self._mode = mode
        self._history: dict[str, deque[SignalAction]] = defaultdict(
            lambda: deque(maxlen=self._required)
        )

    @property
    def consecutive_required(self) -> int:
        return self._required

    @property
    def mode(self) -> str:
        return self._mode

    def set_consecutive_required(self, value: int) -> None:
        """Autopilot — 레짐별 consecutive 조정."""
        n = max(1, int(value))
        if n == self._required:
            return
        self._required = n
        self._history = defaultdict(lambda: deque(maxlen=self._required))

    def set_mode(self, mode: str) -> None:
        """런타임 signal_mode 변경."""
        if mode == self._mode:
            return
        self._mode = mode
        self._history.clear()

    def record(self, symbol: str, action: SignalAction) -> None:
        self._history[symbol].append(action)

    def is_consecutive(self, symbol: str, action: SignalAction) -> bool:
        history = self._history[symbol]
        return len(history) == self._required and all(a == action for a in history)

    def allows_entry(self, symbol: str) -> bool:
        """long_only 호환 — 롱 진입만."""
        return self._mode == "long_only" and self.is_consecutive(
            symbol, SignalAction.BUY
        )

    def allows_entry_action(self, symbol: str, action: SignalAction) -> bool:
        """포지션 없을 때 신규 진입 허용 여부."""
        if action == SignalAction.HOLD:
            return False
        if self._mode == "long_only":
            return action == SignalAction.BUY and self.is_consecutive(
                symbol, SignalAction.BUY
            )
        if self._mode == "long_short":
            if action == SignalAction.BUY:
                return self.is_consecutive(symbol, SignalAction.BUY)
            if action == SignalAction.SELL:
                return self.is_consecutive(symbol, SignalAction.SELL)
        return False

    def allows_long_exit(self, symbol: str) -> bool:
        """롱 포지션 모델 청산 허용."""
        if self._mode not in ("long_only", "long_short"):
            return False
        return self.is_consecutive(symbol, SignalAction.SELL)

    def allows_short_exit(self, symbol: str) -> bool:
        """숏 포지션 모델 청산 허용 (long_short 전용)."""
        if self._mode != "long_short":
            return False
        return self.is_consecutive(symbol, SignalAction.BUY)

    def reset(self, symbol: str) -> None:
        self._history.pop(symbol, None)
