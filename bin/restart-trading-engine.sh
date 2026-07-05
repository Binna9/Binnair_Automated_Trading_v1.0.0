#!/usr/bin/env bash
set -euo pipefail

ROOT="${BINNAIR_STACK_ROOT:-/home/binnair/binnair-stack}"
cd "$ROOT"

docker compose pull trading-engine
docker compose up -d trading-engine

docker compose ps trading-engine
