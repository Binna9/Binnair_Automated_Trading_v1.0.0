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

    # position_snapshot DDL 확장 (기존 DB 호환 migration)
    _migrate_position_snapshot(engine, schema)

    # 모든 이력 테이블에 user_id 추가 (사용자별 이력 분리)
    _migrate_user_id(engine, schema)
    _migrate_futures_order_columns(engine, schema)

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


def _migrate_position_snapshot(engine, schema: str) -> None:
    """trade.position_snapshot에 TP/SL, side 등 컬럼 추가 (ADD COLUMN IF NOT EXISTS)."""
    table = f'"{schema}".position_snapshot'
    alters = [
        ("side", "VARCHAR(16)"),
        ("tp_price", "DOUBLE PRECISION"),
        ("sl_price", "DOUBLE PRECISION"),
        ("status", "VARCHAR(32)"),
        ("opened_at", "TIMESTAMP WITH TIME ZONE"),
        ("closed_at", "TIMESTAMP WITH TIME ZONE"),
        ("realized_pnl", "DOUBLE PRECISION"),
        ("exit_reason", "VARCHAR(32)"),
        ("exit_price", "DOUBLE PRECISION"),
    ]
    with engine.connect() as conn:
        for col, typ in alters:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}"))
        conn.commit()
    print("position_snapshot migration applied.")


def _migrate_user_id(engine, schema: str) -> None:
    """모든 이력/주문 테이블에 user_id VARCHAR(36) 추가. 기존 row는 'default'."""
    tables = [
        "engine_run",
        "strategy_config_snapshot",
        "signal_event",
        "order_request",
        "order_execution",
        "position_snapshot",
        "risk_event",
        "model_inference_event",
        "audit_log",
    ]
    with engine.connect() as conn:
        for tbl in tables:
            table = f'"{schema}"."{tbl}"'
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR(36) DEFAULT 'default'")
            )
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_user_id ON {table} (user_id)")
            )
        conn.commit()
    print("user_id migration applied.")


def _migrate_futures_order_columns(engine, schema: str) -> None:
    """futures/OCO 추적용 order_request/order_execution 컬럼 추가."""
    order_request_table = f'"{schema}"."order_request"'
    order_execution_table = f'"{schema}"."order_execution"'
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {order_request_table} ADD COLUMN IF NOT EXISTS stop_price DOUBLE PRECISION"))
        conn.execute(text(f"ALTER TABLE {order_request_table} ADD COLUMN IF NOT EXISTS reduce_only BOOLEAN DEFAULT FALSE"))
        conn.execute(text(f"ALTER TABLE {order_request_table} ADD COLUMN IF NOT EXISTS position_side VARCHAR(16) DEFAULT 'BOTH'"))
        conn.execute(text(f"ALTER TABLE {order_execution_table} ADD COLUMN IF NOT EXISTS stop_price DOUBLE PRECISION"))
        conn.execute(text(f"ALTER TABLE {order_execution_table} ADD COLUMN IF NOT EXISTS reduce_only BOOLEAN DEFAULT FALSE"))
        conn.execute(text(f"ALTER TABLE {order_execution_table} ADD COLUMN IF NOT EXISTS position_side VARCHAR(16) DEFAULT 'BOTH'"))
        conn.commit()
    print("futures order columns migration applied.")


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
