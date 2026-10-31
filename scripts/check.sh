#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/check_repository.py
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest --junitxml=reports/pytest.xml
uv run --locked python scripts/evaluate_baseline.py
uv run --locked python scripts/evaluate_content.py
uv run --locked python scripts/smoke_distribution.py
