# Recommendation working guide

- Use Python 3.12, FastAPI and uv. Commit uv.lock; sync with --locked.
- Current public contract is GET /health only. Do not imply a trained model exists.
- Keep initialization free of database, model download and external API requirements.
- Validate with ./scripts/check.sh (pytest, Ruff and distribution build).
- Data preparation, content-based recommendations, fallbacks and model evaluation are follow-up work.
- Do not commit datasets, model weights, .venv/, credentials or generated distributions.
- Use PRs and Conventional Commits. Mobile implementation is separately owned.
