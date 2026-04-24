#!/usr/bin/env bash
set -e

MODE="${1:-rest}"
export INTERNAL_MODE="$MODE"

docker compose down
docker compose up -d --build
docker compose --profile bench run --rm benchmark-client
