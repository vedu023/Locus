from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.auth import UserContext, get_current_user
from app.core.errors import AppError
from app.geo.clusters import get_run_cluster_map, get_run_entities_map
from app.geo.normalize import BoundingBox
from app.geo.schemas import RunClustersResponse, RunEntitiesResponse

router = APIRouter(prefix="/runs", tags=["map"])


def _build_bbox(
    min_lat: float | None,
    min_lng: float | None,
    max_lat: float | None,
    max_lng: float | None,
) -> BoundingBox | None:
    values = [min_lat, min_lng, max_lat, max_lng]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise AppError(
            code="INVALID_BBOX",
            message="All bbox parameters must be provided together.",
            status_code=400,
        )
    if min_lat > max_lat or min_lng > max_lng:
        raise AppError(
            code="INVALID_BBOX",
            message="Bounding box minimums must be less than maximums.",
            status_code=400,
        )
    return BoundingBox(
        min_lat=min_lat,
        min_lng=min_lng,
        max_lat=max_lat,
        max_lng=max_lng,
    )


@router.get("/{run_id}/clusters", response_model=RunClustersResponse)
def get_clusters(
    run_id: str,
    zoom: int = Query(default=6, ge=1, le=20),
    entity_type: Literal["company", "person"] | None = None,
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RunClustersResponse:
    bbox = _build_bbox(min_lat, min_lng, max_lat, max_lng)
    return get_run_cluster_map(
        session=session,
        current_user=current_user,
        run_id=run_id,
        zoom=zoom,
        bbox=bbox,
        entity_type=entity_type,
    )


@router.get("/{run_id}/entities", response_model=RunEntitiesResponse)
def get_entities(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    entity_type: Literal["company", "person"] | None = None,
    location_id: str | None = None,
    include_unmapped: bool = False,
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RunEntitiesResponse:
    bbox = _build_bbox(min_lat, min_lng, max_lat, max_lng)
    return get_run_entities_map(
        session=session,
        current_user=current_user,
        run_id=run_id,
        limit=limit,
        offset=offset,
        bbox=bbox,
        entity_type=entity_type,
        location_id=location_id,
        include_unmapped=include_unmapped,
    )
