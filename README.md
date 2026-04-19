# Locus

Python-first backend foundation for the Locus map workbench.

## Phase 0 scope

This repo now targets the Phase 0 foundation:

- FastAPI service entrypoint
- Pydantic settings
- Postgres/PostGIS seam
- SQLAlchemy session management
- Alembic migrations
- Redis seam
- health and auth routes
- pytest + Ruff + CI

## Local setup

```bash
cp .env.example .env
docker compose up -d
uv sync --dev
uv run alembic upgrade head
uv run python main.py
```

## Useful commands

```bash
uv run pytest
uv run ruff check .
uv run alembic current
```

## Environment

Base `.env.example`:

```bash
LOCUS_ENV=development
LOCUS_DEBUG=true
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/locus
REDIS_URL=redis://localhost:6379/0
LOCUS_AUTH_MODE=dev
LOCUS_DEV_USER_ID=dev-user
LOCUS_DEV_USER_EMAIL=dev@locus.local
CRUSTDATA_API_KEY=
CRUSTDATA_API_BASE_URL=https://api.crustdata.com
CRUSTDATA_API_VERSION=2025-11-01
```
