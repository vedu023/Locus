from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.min_lat <= latitude <= self.max_lat and self.min_lng <= longitude <= self.max_lng
        )


def build_point_geojson(latitude: float, longitude: float) -> dict[str, object]:
    return {
        "type": "Point",
        "coordinates": [longitude, latitude],
    }


def cell_size_for_zoom(zoom: int) -> float:
    if zoom >= 12:
        return 0.2
    if zoom >= 10:
        return 0.5
    if zoom >= 8:
        return 1.0
    if zoom >= 6:
        return 2.0
    if zoom >= 4:
        return 5.0
    return 12.0


def cluster_cell(latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
    size = cell_size_for_zoom(zoom)
    return floor((latitude + 90.0) / size), floor((longitude + 180.0) / size)


def is_low_precision(precision: str | None) -> bool:
    return precision in {"region", "country"}
