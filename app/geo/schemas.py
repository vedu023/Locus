from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class BoundingBoxResponse(BaseModel):
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float


class MapSummary(BaseModel):
    total_entities: int
    mapped_count: int
    unmapped_count: int
    low_precision_count: int
    companies: int
    people: int


class MapCluster(BaseModel):
    cluster_id: str
    latitude: float
    longitude: float
    entity_count: int
    company_count: int
    person_count: int
    location_count: int
    low_precision_count: int
    is_cluster: bool
    location_ids: list[str]
    labels: list[str]


class RunClustersResponse(BaseModel):
    run_id: str
    zoom: int
    bbox: BoundingBoxResponse | None
    summary: MapSummary
    clusters: list[MapCluster]


class RunEntityLocation(BaseModel):
    location_id: str | None
    raw_label: str | None
    latitude: float | None
    longitude: float | None
    status: str
    precision: str | None
    confidence: float | None


class RunEntityItem(BaseModel):
    entity_id: str
    entity_type: Literal["company", "person"]
    run_entity_id: str
    name: str
    subtitle: str | None
    location: RunEntityLocation
    rank: int | None
    lens_score: float


class RunEntitiesResponse(BaseModel):
    run_id: str
    summary: MapSummary
    limit: int
    offset: int
    items: list[RunEntityItem]
