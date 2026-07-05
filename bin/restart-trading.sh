#!/usr/bin/env bash
# binnair-stack 서버에서 trading-engine + trading-api 재기동
set -euo pipefail

ROOT="${BINNAIR_STACK_ROOT:-/home/binnair/binnair-stack}"
cd "$ROOT"

docker compose pull trading-engine trading-api
docker compose up -d trading-engine trading-api

docker compose ps trading-engine trading-api
