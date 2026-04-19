from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.auth import UserContext, require_admin
from app.core.operations import ACTION_ENTITY_ENRICH, ACTION_RUN_CREATE, ACTION_WATCHLIST_REFRESH
from app.db.models import SearchRun, Signal, UsageEvent, User, Watchlist, WatchlistItem

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminMetricsResponse(BaseModel):
    users: int
    search_runs: int
    watchlists: int
    watchlist_items: int
    signals: int
    usage_today: dict[str, int]


@router.get("/metrics", response_model=AdminMetricsResponse)
def get_admin_metrics(
    _admin_user: UserContext = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> AdminMetricsResponse:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def count(model) -> int:
        value = session.scalar(select(func.count()).select_from(model))
        return int(value or 0)

    usage = {}
    for action in (ACTION_RUN_CREATE, ACTION_ENTITY_ENRICH, ACTION_WATCHLIST_REFRESH):
        action_count = session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.action == action, UsageEvent.created_at >= today)
        )
        usage[action] = int(action_count or 0)

    return AdminMetricsResponse(
        users=count(User),
        search_runs=count(SearchRun),
        watchlists=count(Watchlist),
        watchlist_items=count(WatchlistItem),
        signals=count(Signal),
        usage_today=usage,
    )
