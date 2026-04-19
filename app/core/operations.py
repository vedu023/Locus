from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import UserContext
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import UsageEvent

ACTION_RUN_CREATE = "run_create"
ACTION_ENTITY_ENRICH = "entity_enrich"
ACTION_WATCHLIST_REFRESH = "watchlist_refresh"

_ACTION_LIMIT_ATTRS = {
    ACTION_RUN_CREATE: "daily_run_limit_per_user",
    ACTION_ENTITY_ENRICH: "daily_enrich_limit_per_user",
    ACTION_WATCHLIST_REFRESH: "daily_refresh_limit_per_user",
}


def _utc_day_start(now: datetime | None = None) -> datetime:
    reference = now or datetime.now(timezone.utc)
    return reference.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def ensure_operation_allowed(
    *,
    session: Session,
    current_user: UserContext,
    action: str,
    increment: int = 1,
) -> None:
    settings = get_settings()
    if settings.global_kill_switch:
        raise AppError(
            code="SERVICE_PAUSED",
            message="Write operations are temporarily paused.",
            status_code=503,
        )

    limit_attr = _ACTION_LIMIT_ATTRS.get(action)
    if limit_attr is None:
        return

    limit = getattr(settings, limit_attr)
    if limit <= 0:
        return

    window_start = _utc_day_start()
    window_end = window_start + timedelta(days=1)
    used = session.scalar(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.auth_provider_id == current_user.user_id,
            UsageEvent.action == action,
            UsageEvent.created_at >= window_start,
            UsageEvent.created_at < window_end,
        )
    )
    current_count = int(used or 0)
    if current_count + increment > limit:
        raise AppError(
            code="QUOTA_EXCEEDED",
            message="Daily quota exceeded for this operation.",
            status_code=429,
            details={
                "action": action,
                "limit": limit,
                "used": current_count,
                "remaining": max(limit - current_count, 0),
            },
        )


def record_usage_event(
    *,
    session: Session,
    current_user: UserContext,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> UsageEvent:
    event = UsageEvent(
        auth_provider_id=current_user.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    session.add(event)
    session.flush()
    return event
