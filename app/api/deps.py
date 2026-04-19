from __future__ import annotations

from functools import lru_cache

from app.crustdata.client import CrustdataClient


@lru_cache
def get_crustdata_client() -> CrustdataClient:
    return CrustdataClient()
