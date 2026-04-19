from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.errors import AppError
from app.crustdata.cache import CacheBackend, build_cache_backend
from app.db.models import Location
from app.geo.normalize import build_point_geojson


@dataclass(frozen=True)
class GeocodeQuery:
    raw_label: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None

    @property
    def query_text(self) -> str:
        if self.raw_label:
            return self.raw_label
        parts = [self.city, self.region, self.country]
        return ", ".join(part for part in parts if part)


@dataclass
class GeocodeResult:
    status: str
    latitude: float | None = None
    longitude: float | None = None
    precision: str | None = None
    confidence: float | None = None
    provider: str | None = None
    error: str | None = None

    def to_payload(self) -> dict[str, object | None]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "GeocodeResult":
        return cls(
            status=str(payload.get("status") or "unmapped"),
            latitude=_float_or_none(payload.get("latitude")),
            longitude=_float_or_none(payload.get("longitude")),
            precision=_string_or_none(payload.get("precision")),
            confidence=_float_or_none(payload.get("confidence")),
            provider=_string_or_none(payload.get("provider")),
            error=_string_or_none(payload.get("error")),
        )


class Geocoder(Protocol):
    def geocode(self, query: GeocodeQuery) -> GeocodeResult: ...

    def close(self) -> None: ...


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_geocode_query(location: Location) -> GeocodeQuery:
    return GeocodeQuery(
        raw_label=location.raw_label,
        city=location.city,
        region=location.region,
        country=location.country,
        country_code=location.country_code,
    )


def apply_geocode_result(location: Location, result: GeocodeResult) -> None:
    location.geocode_status = result.status
    location.geocode_provider = result.provider
    location.geocode_precision = result.precision
    location.geocode_confidence = result.confidence
    location.geocode_error = result.error
    location.latitude = result.latitude
    location.longitude = result.longitude
    if result.latitude is not None and result.longitude is not None:
        location.point_geojson = build_point_geojson(result.latitude, result.longitude)
    else:
        location.point_geojson = None


class NoopGeocoder:
    def geocode(self, query: GeocodeQuery) -> GeocodeResult:
        return GeocodeResult(
            status="unmapped",
            provider="noop",
            error=f"No geocoder configured for '{query.query_text}'.",
        )

    def close(self) -> None:
        return None


class StaticGeocoder:
    def __init__(self, responses: dict[str, GeocodeResult]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def geocode(self, query: GeocodeQuery) -> GeocodeResult:
        key = query.query_text.lower()
        self.calls.append(key)
        return self.responses.get(
            key,
            GeocodeResult(
                status="unmapped",
                provider="static",
                error=f"No static geocode match for '{query.query_text}'.",
            ),
        )

    def close(self) -> None:
        return None


class NominatimGeocoder:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client(
            base_url="https://nominatim.openstreetmap.org",
            headers={"User-Agent": settings.geocoder_user_agent},
            timeout=settings.geocoder_timeout_seconds,
        )

    def geocode(self, query: GeocodeQuery) -> GeocodeResult:
        try:
            response = self.http_client.get(
                "/search",
                params={
                    "format": "jsonv2",
                    "limit": 1,
                    "q": query.query_text,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                code="GEOCODER_NETWORK_ERROR",
                message="Failed to geocode location.",
                status_code=502,
                details={"provider": "nominatim", "error": str(exc)},
            ) from exc

        payload = response.json()
        if not isinstance(payload, list) or not payload:
            return GeocodeResult(
                status="unmapped",
                provider="nominatim",
                error=f"No geocode match for '{query.query_text}'.",
            )

        candidate = payload[0]
        precision = _map_nominatim_precision(_string_or_none(candidate.get("type")))
        latitude = _float_or_none(candidate.get("lat"))
        longitude = _float_or_none(candidate.get("lon"))
        return GeocodeResult(
            status="mapped" if latitude is not None and longitude is not None else "unmapped",
            latitude=latitude,
            longitude=longitude,
            precision=precision,
            confidence=_float_or_none(candidate.get("importance")),
            provider="nominatim",
            error=None,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self.http_client.close()


def _map_nominatim_precision(raw_type: str | None) -> str:
    if raw_type in {"city", "town", "village", "hamlet", "municipality"}:
        return "city"
    if raw_type in {"state", "region", "province", "administrative"}:
        return "region"
    if raw_type == "country":
        return "country"
    return "address"


class CachedGeocoder:
    def __init__(
        self,
        geocoder: Geocoder,
        *,
        cache_backend: CacheBackend | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.geocoder = geocoder
        self.cache_backend = cache_backend or build_cache_backend()
        self.ttl_seconds = ttl_seconds or settings.geocoder_cache_ttl_seconds

    def build_cache_key(self, query: GeocodeQuery) -> str:
        payload = {
            "provider": type(self.geocoder).__name__,
            "query": asdict(query),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"geocode:{digest}"

    def geocode(self, query: GeocodeQuery) -> GeocodeResult:
        cache_key = self.build_cache_key(query)
        cached = self.cache_backend.get(cache_key)
        if cached is not None:
            return GeocodeResult.from_payload(cached)

        result = self.geocoder.geocode(query)
        self.cache_backend.set(cache_key, result.to_payload(), self.ttl_seconds)
        return result

    def close(self) -> None:
        self.geocoder.close()


def build_geocoder() -> CachedGeocoder:
    settings = get_settings()
    if settings.geocoder_provider == "nominatim":
        geocoder: Geocoder = NominatimGeocoder()
    else:
        geocoder = NoopGeocoder()
    return CachedGeocoder(geocoder)
