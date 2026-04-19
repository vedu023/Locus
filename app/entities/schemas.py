from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EntityEnrichResponse(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    last_enriched_at: datetime | None
    signal_count: int = 0


class EntityRawPayloadResponse(BaseModel):
    entity_id: str
    entity_type: str
    raw: dict[str, Any]
