#!/usr/bin/env python3
"""
설정된 Postgres 스키마에 엔진 persistence 테이블을 생성한다.
개발/초기화 시 기존 스키마 삭제 후 재생성도 지원한다.
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


def init_db(drop_existing: bool = False) -> None:
    """테이블 생성. drop_existing=True 시 기존 스키마/테이블 삭제 후 생성."""

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

    _apply_table_comments(engine, schema)

    # position_snapshot DDL 확장 (기존 DB 호환 migration)
    _migrate_position_snapshot(engine, schema)

    # 모든 이력 테이블에 user_id 추가 (사용자별 이력 분리)
    _migrate_user_id(engine, schema)
    _migrate_futures_order_columns(engine, schema)
    _backfill_trade_result_from_snapshots(engine, schema)

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


def _apply_table_comments(engine, schema: str) -> None:
    """PostgreSQL COMMENT ON TABLE 적용 (신규·기존 DB 모두 idempotent)."""
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if table.schema and table.schema != schema:
                continue
            comment = table.comment
            if not comment:
                continue
            qualified = f'"{schema}"."{table.name}"'
            escaped = comment.replace("'", "''")
            conn.execute(text(f"COMMENT ON TABLE {qualified} IS '{escaped}'"))
        conn.commit()
    print("Table comments applied.")


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
        "trade_result",
        "performance_daily",
        "equity_snapshot",
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


def _backfill_trade_result_from_snapshots(engine, schema: str) -> None:
    """기존 position_snapshot CLOSED → trade_result + performance_daily 백필."""
    from binnair_trading_engine.domain.models import Position
    from binnair_trading_engine.performance.metrics import build_trade_result_create
    from binnair_trading_engine.infra.persistence.repositories.postgres import (
        PostgresRepositoryFactory,
    )

    table = f'"{schema}".position_snapshot'
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = 'trade_result'"
            ),
            {"schema": schema},
        ).scalar_one_or_none()
        if not exists:
            return

        rows = conn.execute(
            text(f"""
                SELECT DISTINCT ON (run_id, symbol, closed_at)
                    id, user_id, run_id, strategy_id, symbol, side,
                    quantity, avg_entry_price, exit_price, realized_pnl,
                    exit_reason, opened_at, closed_at, paper_mode
                FROM {table}
                WHERE status = 'CLOSED'
                  AND realized_pnl IS NOT NULL
                  AND closed_at IS NOT NULL
                  AND exit_price IS NOT NULL
                ORDER BY run_id, symbol, closed_at, snapshot_at DESC
            """)
        ).fetchall()

    if not rows:
        print("trade_result backfill: no CLOSED snapshots.")
        return

    repos = PostgresRepositoryFactory()
    inserted = 0
    for row in rows:
        (
            snap_id,
            user_id,
            run_id,
            strategy_id,
            symbol,
            side,
            quantity,
            entry,
            exit_p,
            realized,
            exit_reason,
            opened_at,
            closed_at,
            paper_mode,
        ) = row
        pos = Position(
            symbol=symbol,
            quantity=0.0,
            filled_quantity=float(quantity or 0.0),
            avg_entry_price=float(entry or 0.0),
            side=side or "LONG",
            status="CLOSED",
            opened_at=opened_at,
            closed_at=closed_at,
            run_id=run_id,
            realized_pnl=float(realized or 0.0),
            exit_reason=exit_reason or "",
            exit_price=float(exit_p or 0.0),
        )
        dto = build_trade_result_create(
            pos,
            strategy_id=strategy_id or "",
            user_id=user_id or "default",
            paper_mode=bool(paper_mode),
            position_snapshot_id=int(snap_id),
            trade_id=f"backfill-{snap_id}",
        )
        if dto is None:
            continue
        if repos.trade_result.record_closed_trade(dto) is not None:
            inserted += 1

    print(f"trade_result backfill: {inserted} rows from position_snapshot.")


if __name__ == "__main__":
    from binnair_trading_engine.config.env_loader import load_env_file

    load_env_file()

    parser = argparse.ArgumentParser(description="DB 초기화 (.env.dev / trade.env 기준)")
    parser.add_argument("--drop", action="store_true", help="기존 스키마/테이블 삭제 후 생성")
    args = parser.parse_args()

    init_db(drop_existing=args.drop)
