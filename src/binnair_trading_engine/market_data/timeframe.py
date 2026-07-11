"""Binance interval 문자열 파싱 (numpy/torch 불필요 — API config 로드용)."""

from __future__ import annotations

import re

_TIMEFRAME_RE = re.compile(r"^(\d+)([mhdw])$", re.IGNORECASE)
_UNIT_MINUTES = {"m": 1, "h": 60, "d": 1440, "w": 10080}


def timeframe_to_minutes(timeframe: str) -> float:
    """Binance interval 문자열 → 분 (예: 5m → 5, 1h → 60)."""
    tf = (timeframe or "1m").strip().lower()
    match = _TIMEFRAME_RE.match(tf)
    if not match:
        return 1.0
    amount = int(match.group(1))
    unit = match.group(2).lower()
    return float(amount * _UNIT_MINUTES.get(unit, 1))


def timeframe_to_seconds(timeframe: str) -> int:
    return max(1, int(timeframe_to_minutes(timeframe) * 60))
