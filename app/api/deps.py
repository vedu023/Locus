from __future__ import annotations

from functools import lru_cache

from app.crustdata.client import CrustdataClient
from app.db.session import get_db_session
from app.geo.geocode import CachedGeocoder, build_geocoder


@lru_cache
def get_crustdata_client() -> CrustdataClient:
    return CrustdataClient()


@lru_cache
def get_geocoder() -> CachedGeocoder:
    return build_geocoder()


__all__ = ["get_crustdata_client", "get_db_session", "get_geocoder"]
