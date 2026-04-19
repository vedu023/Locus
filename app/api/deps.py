from __future__ import annotations

from functools import lru_cache

from app.crustdata.client import CrustdataClient
from app.db.session import get_db_session


@lru_cache
def get_crustdata_client() -> CrustdataClient:
    return CrustdataClient()


__all__ = ["get_crustdata_client", "get_db_session"]
