from __future__ import annotations

from app.crustdata.client import CrustdataClient
from app.crustdata.types import (
    AutocompleteRequest,
    AutocompleteResponse,
    CompanySearchRequest,
    EnrichRequest,
    extract_autocomplete_response,
)


class CompanyAutocompleteRequest(AutocompleteRequest):
    pass


def company_autocomplete(
    client: CrustdataClient,
    request: CompanyAutocompleteRequest,
) -> AutocompleteResponse:
    payload = client.post(
        endpoint="/company/search/autocomplete",
        body=request.to_crustdata_payload(),
        cache_ttl_seconds=60 * 60 * 24 * 7,
    )
    return extract_autocomplete_response(payload)


def company_search(client: CrustdataClient, request: CompanySearchRequest) -> dict:
    return client.post(
        endpoint="/company/search",
        body=request.model_dump(exclude_none=True),
        cache_ttl_seconds=60 * 60 * 24,
    )


def company_enrich(client: CrustdataClient, request: EnrichRequest) -> dict:
    return client.post(
        endpoint="/company/enrich",
        body=request.model_dump(exclude_none=True),
        cache_ttl_seconds=60 * 60 * 24 * 14,
    )


def company_identify(client: CrustdataClient, request: EnrichRequest) -> dict:
    return client.post(
        endpoint="/company/identify",
        body=request.model_dump(exclude_none=True),
        cache_ttl_seconds=60 * 60 * 24 * 30,
    )
