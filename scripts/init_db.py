#!/usr/bin/env python3
"""
DB 초기화: 테이블 생성.
config의 storage 설정에서 DB 접속 정보 로드. (CONFIG_PATH 환경변수 사용)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import create_engine, text

from binnair_trading_engine.infra.persistence.models import Base
from binnair_trading_engine.infra.persistence.session import (
    get_database_url,
    get_storage_schema,
)


def init_db(drop_existing: bool = False, config_path: Path | str | None = None) -> None:
    """테이블 생성. drop_existing=True 시 기존 스키마/테이블 삭제 후 생성."""
    if config_path is not None:
        os.environ["CONFIG_PATH"] = str(config_path)

    url = get_database_url()
    schema = get_storage_schema()
    engine = create_engine(url)

    with engine.connect() as conn:
        if drop_existing:
            print("Dropping schema and tables...")
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            conn.commit()
        print("Creating schema if not exists...")
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()

    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Done.")

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema ORDER BY table_name"
            ),
            {"schema": schema},
        )
        tables = [row[0] for row in result]
        print("Tables:", tables)


def _default_config_path() -> Path | None:
    """--config/CONFIG_PATH 미지정 시 기본 config 경로 탐색."""
    root = Path(__file__).resolve().parent.parent
    for name in ("config/config.yaml", "config.yaml"):
        p = root / name
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB 초기화 (config 기반)")
    parser.add_argument("--drop", action="store_true", help="기존 스키마/테이블 삭제 후 생성")
    parser.add_argument("--config", type=str, help="config 파일 경로 (미지정 시 config/config.yaml 탐색)")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else _default_config_path()
    init_db(drop_existing=args.drop, config_path=config_path)
