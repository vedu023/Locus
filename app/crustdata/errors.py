from __future__ import annotations

from typing import Any

from app.core.errors import AppError


def normalize_crustdata_error(status_code: int, payload: Any, endpoint: str) -> AppError:
    details = {
        "endpoint": endpoint,
        "provider": "crustdata",
        "payload": payload,
    }

    if status_code == 400:
        return AppError(
            code="CRUSTDATA_BAD_REQUEST",
            message="Crustdata rejected the request payload.",
            status_code=400,
            details=details,
        )
    if status_code == 401:
        return AppError(
            code="CRUSTDATA_AUTH_FAILED",
            message="Crustdata authentication failed.",
            status_code=502,
            details=details,
        )
    if status_code == 403:
        return AppError(
            code="CRUSTDATA_FORBIDDEN",
            message="Crustdata denied the request.",
            status_code=502,
            details=details,
        )
    if status_code == 429:
        return AppError(
            code="CRUSTDATA_RATE_LIMITED",
            message="Crustdata rate limited the request.",
            status_code=429,
            details=details,
        )
    if status_code >= 500:
        return AppError(
            code="CRUSTDATA_SERVER_ERROR",
            message="Crustdata returned a server error.",
            status_code=502,
            details=details,
        )
    return AppError(
        code="CRUSTDATA_UNKNOWN_ERROR",
        message="Crustdata returned an unexpected error.",
        status_code=502,
        details=details,
    )
