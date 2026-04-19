from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    lens: Literal["sales", "recruiting", "investor"] | None = None
    description: str | None = None


class WatchlistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    lens: Literal["sales", "recruiting", "investor"] | None = None
    description: str | None = None


class WatchlistItemCreateRequest(BaseModel):
    entity_type: Literal["company", "person"]
    company_id: str | None = None
    person_id: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_entity_reference(self) -> "WatchlistItemCreateRequest":
        if self.entity_type == "company":
            if not self.company_id or self.person_id is not None:
                raise ValueError("Company watchlist items require company_id only.")
        if self.entity_type == "person":
            if not self.person_id or self.company_id is not None:
                raise ValueError("Person watchlist items require person_id only.")
        return self


class WatchlistEntitySummary(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    subtitle: str | None
    location_label: str | None


class WatchlistItemResponse(BaseModel):
    item_id: str
    entity: WatchlistEntitySummary
    notes: str | None
    signal_count: int
    created_at: datetime


class WatchlistResponse(BaseModel):
    watchlist_id: str
    name: str
    lens: str | None
    description: str | None
    item_count: int
    items: list[WatchlistItemResponse]
    created_at: datetime
    updated_at: datetime


class WatchlistSignalEntry(BaseModel):
    signal_id: str
    entity_type: str
    entity_id: str | None
    entity_name: str | None
    signal_type: str
    title: str | None
    description: str | None
    confidence: float
    occurred_at: datetime | None
    created_at: datetime


class WatchlistSignalsResponse(BaseModel):
    watchlist_id: str
    signals: list[WatchlistSignalEntry]


class WatchlistRefreshResponse(BaseModel):
    watchlist_id: str
    refreshed_companies: int
    refreshed_people: int
    signals_upserted: int
    skipped: int
