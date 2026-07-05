"""
Postgres DB 엔진과 세션 팩토리를 생성한다.
설정 기반 DATABASE URL과 schema search_path 초기화를 담당한다.
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_SCHEMA = "trade"
_engine_cache = None


def get_database_url() -> str:
    """config의 storage 설정에서 DB URL 반환."""
    from binnair_trading_engine.config import load_config
    return load_config().storage.to_database_url()


def get_storage_schema() -> str:
    """config의 storage.schema 반환."""
    from binnair_trading_engine.config import load_config
    return load_config().storage.schema


def get_engine(schema: str | None = None, echo: bool = False):
    """config 기반 Engine (캐시). schema 미지정 시 config.storage.schema 사용."""
    global _engine_cache
    if _engine_cache is None:
        url = get_database_url()
        s = schema if schema is not None else get_storage_schema()
        _engine_cache = create_engine_from_url(url, schema=s, echo=echo)
    return _engine_cache


def init_db(drop: bool = False) -> None:
    """테이블 생성. drop=True 시 기존 스키마/테이블 삭제 후 생성."""
    schema = get_storage_schema()
    engine = get_engine()
    with engine.connect() as conn:
        if drop:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()
    Base.metadata.create_all(bind=engine)


def create_engine_from_url(
    url: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    echo: bool = False,
):
    """엔진 생성. 매 연결마다 search_path 설정."""
    from sqlalchemy import event

    engine = create_engine(
        url,
        echo=echo,
        future=True,
    )
    if schema and schema != "public":

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_conn, connection_record):
            with dbapi_conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}")
                cur.execute("SET timezone TO 'Asia/Seoul'")

    return engine


def get_session_factory(engine: "sqlalchemy.Engine") -> sessionmaker[Session]:
    """SessionFactory 반환."""
    return sessionmaker(
        engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """세션 컨텍스트 매니저."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
