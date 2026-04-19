from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_crustdata_client
from app.crustdata.client import CrustdataClient
from app.crustdata.company import CompanyAutocompleteRequest, company_autocomplete
from app.crustdata.person import PersonAutocompleteRequest, person_autocomplete
from app.crustdata.types import AutocompleteResponse

router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


@router.post("/company", response_model=AutocompleteResponse)
def autocomplete_company(
    request: CompanyAutocompleteRequest,
    client: CrustdataClient = Depends(get_crustdata_client),
) -> AutocompleteResponse:
    return company_autocomplete(client, request)


@router.post("/person", response_model=AutocompleteResponse)
def autocomplete_person(
    request: PersonAutocompleteRequest,
    client: CrustdataClient = Depends(get_crustdata_client),
) -> AutocompleteResponse:
    return person_autocomplete(client, request)
