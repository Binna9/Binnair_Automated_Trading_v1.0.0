#!/usr/bin/env python3
"""
OHLCV 적재 루프와 자동매매 엔진을 한 번에 실행한다.

기본 동작:
1. .env.dev / trade.env 에서 symbol/timeframe/주기를 읽는다.
2. 시작 시 OHLCV 백필(최근 1000개) 1회 실행.
3. ingest_ohlcv.py --loop 백그라운드 실행.
4. binnair_trading_engine.app.main 포그라운드 실행.
5. Ctrl+C 시 두 프로세스 모두 종료.

사용 예:
  .venv/bin/python scripts/run_engine.py
  .venv/bin/python scripts/run_engine.py --ingest-only
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logger = logging.getLogger("run_engine")

PROCS: list[subprocess.Popen] = []
_ENGINE_PROC: subprocess.Popen | None = None
_SHUTTING_DOWN = False
_GRACE_SECONDS = 15

if sys.platform == "win32":
    _CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
else:
    _CREATE_NEW_PROCESS_GROUP = 0


def _python_bin() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _mark_engine_stopped() -> None:
    """자식이 강제 종료돼 stop() 못 탔을 때 engine_run status 보정."""
    try:
        from binnair_trading_engine.config import load_config
        from binnair_trading_engine.storage import create_storage

        cfg = load_config()
        if cfg.storage.backend != "postgres":
            return
        storage = create_storage(cfg)
        if hasattr(storage, "record_engine_stop"):
            storage.record_engine_stop(cfg.run_context.run_id, "stopped")
            logger.info(
                "Marked engine_run stopped (fallback): run_id=%s",
                cfg.run_context.run_id,
            )
    except Exception:
        logger.exception("Failed to mark engine_run as stopped")


def _request_graceful_stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
    except Exception as e:
        logger.warning("Graceful stop signal failed, terminating: %s", e)
        proc.terminate()


def _shutdown(exit_code: int = 0) -> None:
    global _SHUTTING_DOWN
    if _SHUTTING_DOWN:
        return
    _SHUTTING_DOWN = True
    logger.info("Shutting down child processes...")

    # 엔진 먼저 graceful 종료 (DB status=stopped, flatten_on_shutdown)
    if _ENGINE_PROC is not None and _ENGINE_PROC.poll() is None:
        _request_graceful_stop(_ENGINE_PROC)
        deadline = time.time() + _GRACE_SECONDS
        while _ENGINE_PROC.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if _ENGINE_PROC.poll() is None:
            logger.warning("Engine did not exit in %ss, killing", _GRACE_SECONDS)
            _ENGINE_PROC.kill()

    if _ENGINE_PROC is not None:
        _mark_engine_stopped()

    for proc in PROCS:
        if proc is _ENGINE_PROC:
            continue
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 5
    for proc in PROCS:
        if proc is _ENGINE_PROC:
            continue
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if proc.poll() is None:
            proc.kill()
    raise SystemExit(exit_code)


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("Received signal %s", signum)
    _shutdown(0)


def _run_backfill(
    python_bin: str,
    symbol: str,
    timeframe: str,
    base_url: str,
    limit: int,
) -> None:
    cmd = [
        python_bin,
        str(ROOT / "scripts" / "ingest_ohlcv.py"),
        "--symbol",
        symbol,
        "--timeframe",
        timeframe,
        "--limit",
        str(limit),
        "--base-url",
        base_url,
    ]
    logger.info("Running OHLCV backfill: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, env=os.environ.copy(), check=True)


def _start_ingest(
    python_bin: str,
    symbol: str,
    timeframe: str,
    poll_interval: float,
    base_url: str,
    limit: int,
) -> subprocess.Popen:
    cmd = [
        python_bin,
        str(ROOT / "scripts" / "ingest_ohlcv.py"),
        "--symbol",
        symbol,
        "--timeframe",
        timeframe,
        "--limit",
        str(limit),
        "--base-url",
        base_url,
        "--loop",
        "--poll-interval",
        str(poll_interval),
    ]
    logger.info("Starting OHLCV loop: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=ROOT, env=os.environ.copy())
    PROCS.append(proc)
    return proc


def _start_engine(python_bin: str) -> subprocess.Popen:
    global _ENGINE_PROC
    cmd = [python_bin, "-m", "binnair_trading_engine.app.main"]
    logger.info("Starting trading engine: %s", " ".join(cmd))
    popen_kw: dict = {"cwd": ROOT, "env": os.environ.copy()}
    if sys.platform == "win32":
        popen_kw["creationflags"] = _CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(cmd, **popen_kw)
    PROCS.append(proc)
    _ENGINE_PROC = proc
    return proc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OHLCV ingestion loop and trading engine together.",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Skip one-time OHLCV backfill on startup.",
    )
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Run only OHLCV ingestion loop.",
    )
    parser.add_argument(
        "--engine-only",
        action="store_true",
        help="Run only trading engine (OHLCV loop skipped).",
    )
    parser.add_argument(
        "--backfill-limit",
        type=int,
        default=1000,
        help="Number of candles for startup backfill (default: 1000).",
    )
    parser.add_argument(
        "--ingest-limit",
        type=int,
        default=500,
        help="Number of candles fetched per loop iteration (default: 500).",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    )

    args = parse_args()
    if args.ingest_only and args.engine_only:
        logger.error("--ingest-only and --engine-only cannot be used together.")
        return 1

    from binnair_trading_engine.config import load_config

    cfg = load_config()
    symbol = cfg.market_data.symbol
    timeframe = (
        cfg.predictor_timesfm_config.timeframe
        if cfg.predictor_timesfm_config
        else "1m"
    )
    poll_interval = cfg.market_data.poll_interval_seconds
    base_url = cfg.market_data.base_url
    python_bin = _python_bin()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    run_ingest = not args.engine_only
    run_engine = not args.ingest_only

    if run_ingest and not args.no_backfill:
        _run_backfill(
            python_bin=python_bin,
            symbol=symbol,
            timeframe=timeframe,
            base_url=base_url,
            limit=args.backfill_limit,
        )

    if run_ingest:
        _start_ingest(
            python_bin=python_bin,
            symbol=symbol,
            timeframe=timeframe,
            poll_interval=poll_interval,
            base_url=base_url,
            limit=args.ingest_limit,
        )

    if run_engine:
        _start_engine(python_bin=python_bin)

    if not PROCS:
        logger.error("No process started.")
        return 1

    logger.info(
        "All processes started. symbol=%s timeframe=%s poll=%.1fs (Ctrl+C to stop)",
        symbol,
        timeframe,
        poll_interval,
    )

    try:
        while True:
            for proc in PROCS:
                rc = proc.poll()
                if rc is not None:
                    name = proc.args[1] if len(proc.args) > 1 else "child"
                    logger.error("Process exited unexpectedly: %s (code=%s)", name, rc)
                    _shutdown(rc if rc is not None else 1)
            time.sleep(1)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
