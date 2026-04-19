from __future__ import annotations

from app.crustdata.client import CrustdataClient
from app.crustdata.types import (
    AutocompleteRequest,
    AutocompleteResponse,
    EnrichRequest,
    PersonSearchRequest,
    extract_autocomplete_response,
)


class PersonAutocompleteRequest(AutocompleteRequest):
    pass


def person_autocomplete(
    client: CrustdataClient,
    request: PersonAutocompleteRequest,
) -> AutocompleteResponse:
    payload = client.post(
        endpoint="/person/search/autocomplete",
        body=request.to_crustdata_payload(),
        cache_ttl_seconds=60 * 60 * 24 * 7,
    )
    return extract_autocomplete_response(payload)


def person_search(client: CrustdataClient, request: PersonSearchRequest) -> dict:
    return client.post(
        endpoint="/person/search",
        body=request.model_dump(exclude_none=True),
        cache_ttl_seconds=60 * 60 * 24,
    )


def person_enrich(client: CrustdataClient, request: EnrichRequest) -> dict:
    return client.post(
        endpoint="/person/enrich",
        body=request.model_dump(exclude_none=True),
        cache_ttl_seconds=60 * 60 * 24 * 14,
    )
