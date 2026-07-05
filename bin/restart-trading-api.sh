#!/usr/bin/env bash
set -euo pipefail

ROOT="${BINNAIR_STACK_ROOT:-/home/binnair/binnair-stack}"
cd "$ROOT"

docker compose pull trading-api
docker compose up -d trading-api

docker compose ps trading-api
