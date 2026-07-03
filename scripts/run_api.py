#!/usr/bin/env python3
"""BinnAIR 조회 API 서버 실행."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.api.main import run
from binnair_trading_engine.config import load_config


def _default_config_path() -> Path | None:
    root = Path(__file__).resolve().parent.parent
    for name in ("config/config.yaml", "config.yaml"):
        p = root / name
        if p.exists():
            return p
    return None


def _pids_on_port_windows(port: int) -> set[int]:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pids: set[int] = set()
    port_suffix = f":{port}"
    for line in result.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        if not local_addr.endswith(port_suffix):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return pids


def _pids_on_port_unix(port: int) -> set[int]:
    for cmd in (
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        ["fuser", f"{port}/tcp"],
    ):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 and not result.stdout.strip():
            continue
        pids: set[int] = set()
        for token in re.split(r"[\s,]+", result.stdout.strip()):
            if token.isdigit():
                pids.add(int(token))
        if pids:
            return pids
    return set()


def kill_process_on_port(port: int) -> list[int]:
    """지정 포트 LISTEN 중인 프로세스 종료. 종료한 PID 목록 반환."""
    if port <= 0:
        return []

    if sys.platform == "win32":
        pids = _pids_on_port_windows(port)
    else:
        pids = _pids_on_port_unix(port)

    killed: list[int] = []
    for pid in sorted(pids):
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ok = result.returncode == 0
        else:
            result = subprocess.run(
                ["kill", "-9", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            ok = result.returncode == 0

        if ok:
            killed.append(pid)
            print(f"Stopped PID {pid} (port {port} in use)")
        else:
            err = (result.stderr or result.stdout or "").strip()
            print(f"Failed to stop PID {pid} on port {port}: {err}")

    if killed:
        time.sleep(0.3)
    return killed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BinnAIR monitor API (read-only)")
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host (default: config.api.host)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: config.api.port)",
    )
    parser.add_argument("--config", type=str, help="config YAML 경로")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else _default_config_path()
    if config_path is not None:
        os.environ["CONFIG_PATH"] = str(config_path)

    cfg = load_config(config_path)
    if not cfg.api.enabled:
        print("api.enabled=false — API 서버를 시작하지 않습니다.")
        sys.exit(0)

    bind_port = args.port if args.port is not None else cfg.api.port
    bind_host = args.host if args.host is not None else cfg.api.host

    kill_process_on_port(bind_port)
    print(f"Starting API on http://{bind_host}:{bind_port}")
    run(host=bind_host, port=bind_port)
