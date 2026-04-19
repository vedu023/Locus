from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy import text

from app.core.redis_client import get_redis_client
from app.db.session import get_engine


def check_database() -> dict[str, Any]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_redis() -> dict[str, Any]:
    try:
        get_redis_client().ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def build_readiness_report() -> tuple[dict[str, Any], int]:
    checks = {
        "database": check_database(),
        "redis": check_redis(),
    }
    overall_status = (
        "ok" if all(item["status"] == "ok" for item in checks.values()) else "degraded"
    )
    status_code = (
        status.HTTP_200_OK
        if overall_status == "ok"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {"status": overall_status, "checks": checks}, status_code
