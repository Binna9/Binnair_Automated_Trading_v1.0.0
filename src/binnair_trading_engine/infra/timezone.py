"""
애플리케이션 기본 시간대(KST) 유틸.

DB 컬럼은 TIMESTAMP WITH TIME ZONE 이므로 instant는 동일하게 저장되며,
insert 시 KST(+09:00) aware datetime을 사용해 조회·로그가 한국 시간과 일치하게 한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """현재 시각 (Asia/Seoul, timezone-aware)."""
    return datetime.now(KST)


def ensure_kst(dt: datetime | None) -> datetime:
    """
    DB 저장용 datetime을 KST aware로 정규화한다.
    naive datetime은 기존 코드 관례대로 UTC로 해석한 뒤 KST로 변환한다.
    """
    if dt is None:
        return now_kst()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def kst_today_start() -> datetime:
    """오늘 00:00:00 (KST). 일별 PnL·집계 경계용."""
    now = now_kst()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
