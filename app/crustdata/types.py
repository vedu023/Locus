from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.crustdata.filters import FilterCondition, FilterGroup, filter_to_payload


class AutocompleteSuggestion(BaseModel):
    value: str


class AutocompleteResponse(BaseModel):
    suggestions: list[AutocompleteSuggestion]


class AutocompleteRequest(BaseModel):
    field: str
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: FilterCondition | FilterGroup | None = None

    def to_crustdata_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "field": self.field,
            "query": self.query,
            "limit": self.limit,
        }
        if self.filters is not None:
            payload["filters"] = filter_to_payload(self.filters)
        return payload


class SearchRequest(BaseModel):
    filters: FilterCondition | FilterGroup | None = None
    fields: list[str] = Field(min_length=1)
    limit: int = Field(default=100, ge=1, le=300)
    cursor: str | None = None

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:  # type: ignore[override]
        payload = super().model_dump(*args, **kwargs)
        if self.filters is not None:
            payload["filters"] = filter_to_payload(self.filters)
        return payload


class CompanySearchRequest(SearchRequest):
    pass


class PersonSearchRequest(SearchRequest):
    pass


class EnrichRequest(BaseModel):
    ids: list[str] | None = None
    domains: list[str] | None = None
    profile_urls: list[str] | None = None
    fields: list[str] | None = None


def _coerce_suggestion(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("value", "label", "name", "title"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def extract_autocomplete_response(payload: dict[str, Any]) -> AutocompleteResponse:
    candidates: Any = payload.get("suggestions")
    if candidates is None:
        for key in ("data", "results", "items"):
            if key in payload:
                candidates = payload[key]
                break

    if not isinstance(candidates, list):
        candidates = []

    suggestions = []
    for item in candidates:
        value = _coerce_suggestion(item)
        if value:
            suggestions.append(AutocompleteSuggestion(value=value))

    return AutocompleteResponse(suggestions=suggestions)
