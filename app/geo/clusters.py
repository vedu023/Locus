from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import UserContext
from app.db.models import Company, Person, SearchRunEntity
from app.geo.normalize import BoundingBox, cluster_cell, is_low_precision
from app.geo.schemas import (
    BoundingBoxResponse,
    MapCluster,
    MapSummary,
    RunClustersResponse,
    RunEntitiesResponse,
    RunEntityItem,
    RunEntityLocation,
)
from app.runs.service import get_search_run


@dataclass
class EntityMapRecord:
    run_entity_id: str
    entity_id: str
    entity_type: Literal["company", "person"]
    name: str
    subtitle: str | None
    location_id: str | None
    location_label: str | None
    latitude: float | None
    longitude: float | None
    location_status: str
    location_precision: str | None
    location_confidence: float | None
    rank: int | None
    lens_score: float

    @property
    def is_mapped(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
            and self.location_status == "mapped"
        )

    @property
    def is_low_precision(self) -> bool:
        return is_low_precision(self.location_precision)


@dataclass
class ClusterAccumulator:
    cluster_id: str
    entity_count: int = 0
    company_count: int = 0
    person_count: int = 0
    low_precision_count: int = 0
    latitude_total: float = 0.0
    longitude_total: float = 0.0
    location_ids: set[str] = field(default_factory=set)
    labels: set[str] = field(default_factory=set)

    def add(self, record: EntityMapRecord) -> None:
        self.entity_count += 1
        self.company_count += int(record.entity_type == "company")
        self.person_count += int(record.entity_type == "person")
        self.low_precision_count += int(record.is_low_precision)
        self.latitude_total += record.latitude or 0.0
        self.longitude_total += record.longitude or 0.0
        if record.location_id:
            self.location_ids.add(record.location_id)
        if record.location_label:
            self.labels.add(record.location_label)

    def to_model(self) -> MapCluster:
        divisor = self.entity_count or 1
        location_ids = sorted(self.location_ids)
        labels = sorted(self.labels)[:3]
        return MapCluster(
            cluster_id=self.cluster_id,
            latitude=self.latitude_total / divisor,
            longitude=self.longitude_total / divisor,
            entity_count=self.entity_count,
            company_count=self.company_count,
            person_count=self.person_count,
            location_count=len(location_ids),
            low_precision_count=self.low_precision_count,
            is_cluster=self.entity_count > 1 or len(location_ids) > 1,
            location_ids=location_ids,
            labels=labels,
        )


def _summary(records: list[EntityMapRecord]) -> MapSummary:
    return MapSummary(
        total_entities=len(records),
        mapped_count=sum(1 for record in records if record.is_mapped),
        unmapped_count=sum(1 for record in records if not record.is_mapped),
        low_precision_count=sum(1 for record in records if record.is_low_precision),
        companies=sum(1 for record in records if record.entity_type == "company"),
        people=sum(1 for record in records if record.entity_type == "person"),
    )


def _to_location_model(record: EntityMapRecord) -> RunEntityLocation:
    return RunEntityLocation(
        location_id=record.location_id,
        raw_label=record.location_label,
        latitude=record.latitude,
        longitude=record.longitude,
        status=record.location_status,
        precision=record.location_precision,
        confidence=record.location_confidence,
    )


def _entity_name(
    entity_type: str, company: Company | None, person: Person | None
) -> tuple[str, str | None]:
    if entity_type == "company":
        if company is None:
            return "Unknown company", None
        return company.name, company.primary_domain

    if person is None:
        return "Unknown person", None
    return person.name, person.current_title


def _records_for_run(
    *,
    session: Session,
    current_user: UserContext,
    run_id: str,
) -> list[EntityMapRecord]:
    run = get_search_run(session=session, current_user=current_user, run_id=run_id)

    entities = session.scalars(
        select(SearchRunEntity)
        .where(SearchRunEntity.run_id == run.id)
        .options(
            joinedload(SearchRunEntity.company),
            joinedload(SearchRunEntity.person),
            joinedload(SearchRunEntity.location),
        )
        .order_by(SearchRunEntity.rank.asc().nullslast(), SearchRunEntity.created_at.asc())
    ).all()

    records: list[EntityMapRecord] = []
    for entity in entities:
        location = entity.location
        name, subtitle = _entity_name(entity.entity_type, entity.company, entity.person)
        records.append(
            EntityMapRecord(
                run_entity_id=entity.id,
                entity_id=entity.company_id or entity.person_id or entity.id,
                entity_type=entity.entity_type,
                name=name,
                subtitle=subtitle,
                location_id=entity.location_id,
                location_label=location.raw_label if location else None,
                latitude=location.latitude if location else None,
                longitude=location.longitude if location else None,
                location_status=location.geocode_status if location else "missing",
                location_precision=location.geocode_precision if location else None,
                location_confidence=location.geocode_confidence if location else None,
                rank=entity.rank,
                lens_score=entity.lens_score,
            )
        )

    return records


def _filter_records(
    records: list[EntityMapRecord],
    *,
    bbox: BoundingBox | None = None,
    entity_type: Literal["company", "person"] | None = None,
    location_id: str | None = None,
    include_unmapped: bool = False,
) -> list[EntityMapRecord]:
    filtered: list[EntityMapRecord] = []
    for record in records:
        if entity_type and record.entity_type != entity_type:
            continue
        if location_id and record.location_id != location_id:
            continue
        if not include_unmapped and not record.is_mapped:
            continue
        if bbox is not None and record.is_mapped:
            if not bbox.contains(record.latitude or 0.0, record.longitude or 0.0):
                continue
        if bbox is not None and not record.is_mapped and not include_unmapped:
            continue
        filtered.append(record)
    return filtered


def get_run_cluster_map(
    *,
    session: Session,
    current_user: UserContext,
    run_id: str,
    zoom: int,
    bbox: BoundingBox | None = None,
    entity_type: Literal["company", "person"] | None = None,
) -> RunClustersResponse:
    records = _records_for_run(session=session, current_user=current_user, run_id=run_id)
    visible_records = _filter_records(
        records,
        bbox=bbox,
        entity_type=entity_type,
        include_unmapped=False,
    )

    clusters: dict[tuple[int, int], ClusterAccumulator] = {}
    for record in visible_records:
        if record.latitude is None or record.longitude is None:
            continue
        cell = cluster_cell(record.latitude, record.longitude, zoom)
        cluster_id = f"{zoom}:{cell[0]}:{cell[1]}"
        accumulator = clusters.setdefault(cell, ClusterAccumulator(cluster_id=cluster_id))
        accumulator.add(record)

    return RunClustersResponse(
        run_id=run_id,
        zoom=zoom,
        bbox=(
            BoundingBoxResponse(
                min_lat=bbox.min_lat,
                min_lng=bbox.min_lng,
                max_lat=bbox.max_lat,
                max_lng=bbox.max_lng,
            )
            if bbox is not None
            else None
        ),
        summary=_summary(records),
        clusters=sorted(
            (accumulator.to_model() for accumulator in clusters.values()),
            key=lambda cluster: (-cluster.entity_count, cluster.cluster_id),
        ),
    )


def get_run_entities_map(
    *,
    session: Session,
    current_user: UserContext,
    run_id: str,
    limit: int,
    offset: int,
    bbox: BoundingBox | None = None,
    entity_type: Literal["company", "person"] | None = None,
    location_id: str | None = None,
    include_unmapped: bool = False,
) -> RunEntitiesResponse:
    records = _records_for_run(session=session, current_user=current_user, run_id=run_id)
    filtered = _filter_records(
        records,
        bbox=bbox,
        entity_type=entity_type,
        location_id=location_id,
        include_unmapped=include_unmapped,
    )

    items = [
        RunEntityItem(
            entity_id=record.entity_id,
            entity_type=record.entity_type,
            run_entity_id=record.run_entity_id,
            name=record.name,
            subtitle=record.subtitle,
            location=_to_location_model(record),
            rank=record.rank,
            lens_score=record.lens_score,
        )
        for record in filtered[offset : offset + limit]
    ]

    return RunEntitiesResponse(
        run_id=run_id,
        summary=_summary(records),
        limit=limit,
        offset=offset,
        items=items,
    )
