from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Location, SearchRun, SearchRunEntity
from app.geo.geocode import Geocoder, GeocodeResult, apply_geocode_result, build_geocode_query
from app.geo.normalize import is_low_precision


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def geocode_pending_locations(
    *,
    session: Session,
    geocoder: Geocoder,
    location_ids: list[str] | None = None,
    limit: int = 100,
) -> list[str]:
    stmt = select(Location).where(Location.geocode_status != "mapped").limit(limit)
    if location_ids is not None:
        stmt = stmt.where(Location.id.in_(location_ids))

    locations = session.scalars(stmt).all()
    updated: list[str] = []
    for location in locations:
        try:
            result = geocoder.geocode(build_geocode_query(location))
        except Exception as exc:
            result = GeocodeResult(
                status="failed",
                provider=type(geocoder).__name__,
                error=str(exc),
            )
        apply_geocode_result(location, result)
        location.geocoded_at = _utcnow()
        updated.append(location.id)

    session.flush()
    return updated


def update_run_geo_summary(session: Session, run_id: str) -> None:
    entities = session.scalars(
        select(SearchRunEntity).where(SearchRunEntity.run_id == run_id)
    ).all()

    mapped = 0
    unmapped = 0
    low_precision = 0
    mapped_locations: set[str] = set()
    low_precision_locations: set[str] = set()

    for entity in entities:
        if entity.location is None:
            unmapped += 1
            continue
        if entity.location.geocode_status != "mapped":
            unmapped += 1
            continue

        mapped += 1
        mapped_locations.add(entity.location.id)
        if is_low_precision(entity.location.geocode_precision):
            low_precision += 1
            low_precision_locations.add(entity.location.id)

    run = session.get(SearchRun, run_id)
    if run is None:
        return

    counts = dict(run.result_counts or {})
    counts.update(
        {
            "mapped": mapped,
            "unmapped": unmapped,
            "low_precision": low_precision,
            "mapped_locations": len(mapped_locations),
            "low_precision_locations": len(low_precision_locations),
        }
    )
    run.result_counts = counts


def geocode_run_locations(
    *,
    session_factory: sessionmaker[Session],
    geocoder: Geocoder,
    run_id: str,
) -> None:
    with session_factory() as session:
        location_ids = [
            location_id
            for location_id in session.scalars(
                select(SearchRunEntity.location_id).where(
                    SearchRunEntity.run_id == run_id,
                    SearchRunEntity.location_id.is_not(None),
                )
            ).all()
            if location_id is not None
        ]

        if location_ids:
            geocode_pending_locations(
                session=session,
                geocoder=geocoder,
                location_ids=sorted(set(location_ids)),
                limit=len(location_ids),
            )

        update_run_geo_summary(session, run_id)
        session.commit()
