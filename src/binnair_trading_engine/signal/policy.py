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

    1차 정책은 long_only:
    - BUY N회 연속: 신규 롱 진입 허용
    - SELL N회 연속: 보유 롱 청산 허용
    - HOLD: 포지션 유지
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

    def record(self, symbol: str, action: SignalAction) -> None:
        self._history[symbol].append(action)

    def is_consecutive(self, symbol: str, action: SignalAction) -> bool:
        history = self._history[symbol]
        return len(history) == self._required and all(a == action for a in history)

    def allows_entry(self, symbol: str) -> bool:
        """현재 정책에서 신규 진입을 허용하는지."""
        return self._mode == "long_only" and self.is_consecutive(symbol, SignalAction.BUY)

    def allows_long_exit(self, symbol: str) -> bool:
        """현재 정책에서 롱 포지션 청산을 허용하는지."""
        return self._mode == "long_only" and self.is_consecutive(symbol, SignalAction.SELL)

    def reset(self, symbol: str) -> None:
        self._history.pop(symbol, None)
