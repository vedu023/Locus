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

    return UserContext(
        user_id=user_id,
        email=email,
        auth_mode=settings.auth_mode,
        is_admin=True,
    )
