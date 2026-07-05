"""쿼리 파라미터 날짜·시각 파싱."""

from __future__ import annotations

from datetime import date, datetime


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)
