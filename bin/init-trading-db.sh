#!/usr/bin/env bash
# trading-engine 컨테이너에서 init_db 실행 (env/trade.env 기준)
set -euo pipefail

ROOT="${BINNAIR_STACK_ROOT:-/home/binnair/binnair-stack}"
cd "$ROOT"

docker compose exec trading-engine python scripts/init_db.py "$@"
