#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --locked uvicorn pubburi_recommendation.main:app --host 127.0.0.1 --port 8000 --reload
