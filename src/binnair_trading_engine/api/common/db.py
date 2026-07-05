"""
API 전용 Postgres 세션.

BINNAIR_STORAGE_* 환경변수로 DB에 연결해 Session을 반환한다.

왜 필요: repository가 SQL을 실행하려면 DB 연결이 필요하다.
엔진 write repository 와 분리해 API는 read-only 세션만 쓴다.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from binnair_trading_engine.infra.persistence.session import get_engine, get_session_factory

_session_factory_cache = None


def get_db_session() -> Session:
    global _session_factory_cache
    if _session_factory_cache is None:
        _session_factory_cache = get_session_factory(get_engine())
    return _session_factory_cache()
