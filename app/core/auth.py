from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AppError


class UserContext(BaseModel):
    user_id: str
    email: str | None = None
    auth_mode: str
    is_admin: bool = False


def _parse_csv(raw: str) -> set[str]:
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def get_current_user(request: Request) -> UserContext:
    settings = get_settings()

    if settings.auth_mode == "disabled":
        return UserContext(
            user_id="anonymous",
            email=None,
            auth_mode=settings.auth_mode,
            is_admin=False,
        )

    user_id = request.headers.get("X-Dev-User-ID", settings.dev_user_id)
    email = request.headers.get("X-Dev-User-Email", settings.dev_user_email)

    if not user_id:
        raise AppError(
            code="UNAUTHENTICATED",
            message="Development auth is enabled but no user identity is available.",
            status_code=401,
        )

    admin_override = _parse_bool(request.headers.get("X-Dev-User-Is-Admin"))
    if admin_override is not None:
        is_admin = admin_override
    else:
        admin_user_ids = _parse_csv(settings.admin_user_ids)
        admin_user_emails = _parse_csv(settings.admin_user_emails)
        normalized_email = (email or "").strip().lower()
        is_admin = (
            user_id == settings.dev_user_id
            or normalized_email == settings.dev_user_email.strip().lower()
            or user_id.strip().lower() in admin_user_ids
            or normalized_email in admin_user_emails
        )

    return UserContext(
        user_id=user_id,
        email=email,
        auth_mode=settings.auth_mode,
        is_admin=is_admin,
    )


def require_admin(request: Request) -> UserContext:
    current_user = get_current_user(request)
    if not current_user.is_admin:
        raise AppError(
            code="FORBIDDEN",
            message="Admin access is required for this endpoint.",
            status_code=403,
        )
    return current_user
