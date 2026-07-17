"""목록 API 공통 페이지 응답."""

from __future__ import annotations

from typing import Any, Sequence


def page_response(
    items: Sequence[Any],
    *,
    total_count: int,
    offset: int,
    limit: int,
    **extra: Any,
) -> dict[str, Any]:
    """프론트 포워딩용 표준 페이지 래퍼."""
    count = len(items)
    return {
        "items": items,
        "count": count,
        "total_count": int(total_count),
        "offset": int(offset),
        "limit": int(limit),
        "has_more": int(offset) + count < int(total_count),
        **extra,
    }


def clamp_limit(limit: int, *, lo: int = 1, hi: int = 500) -> int:
    return max(lo, min(int(limit), hi))


def clamp_offset(offset: int) -> int:
    return max(0, int(offset))
