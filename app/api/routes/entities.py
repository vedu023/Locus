from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_crustdata_client, get_db_session
from app.core.auth import UserContext, get_current_user, require_admin
from app.core.operations import (
    ACTION_ENTITY_ENRICH,
    ensure_operation_allowed,
    record_usage_event,
)
from app.crustdata.client import CrustdataClient
from app.entities.schemas import EntityEnrichResponse, EntityRawPayloadResponse
from app.entities.service import (
    enrich_company_entity,
    enrich_person_entity,
    get_company_or_404,
    get_person_or_404,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.post("/company/{company_id}/enrich", response_model=EntityEnrichResponse)
def enrich_company_route(
    company_id: str,
    current_user: UserContext = Depends(get_current_user),
    client: CrustdataClient = Depends(get_crustdata_client),
    session: Session = Depends(get_db_session),
) -> EntityEnrichResponse:
    ensure_operation_allowed(
        session=session,
        current_user=current_user,
        action=ACTION_ENTITY_ENRICH,
    )
    company, signal_count = enrich_company_entity(
        session=session,
        client=client,
        company_id=company_id,
    )
    record_usage_event(
        session=session,
        current_user=current_user,
        action=ACTION_ENTITY_ENRICH,
        target_type="company",
        target_id=company.id,
        details={"signal_count": signal_count},
    )
    session.commit()
    return EntityEnrichResponse(
        entity_id=company.id,
        entity_type="company",
        name=company.name,
        last_enriched_at=company.last_enriched_at,
        signal_count=signal_count,
    )


@router.post("/person/{person_id}/enrich", response_model=EntityEnrichResponse)
def enrich_person_route(
    person_id: str,
    current_user: UserContext = Depends(get_current_user),
    client: CrustdataClient = Depends(get_crustdata_client),
    session: Session = Depends(get_db_session),
) -> EntityEnrichResponse:
    ensure_operation_allowed(
        session=session,
        current_user=current_user,
        action=ACTION_ENTITY_ENRICH,
    )
    person = enrich_person_entity(session=session, client=client, person_id=person_id)
    record_usage_event(
        session=session,
        current_user=current_user,
        action=ACTION_ENTITY_ENRICH,
        target_type="person",
        target_id=person.id,
    )
    session.commit()
    return EntityEnrichResponse(
        entity_id=person.id,
        entity_type="person",
        name=person.name,
        last_enriched_at=person.last_enriched_at,
        signal_count=0,
    )


@router.get("/company/{company_id}/raw", response_model=EntityRawPayloadResponse)
def get_company_raw(
    company_id: str,
    _admin_user: UserContext = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> EntityRawPayloadResponse:
    company = get_company_or_404(session, company_id)
    return EntityRawPayloadResponse(entity_id=company.id, entity_type="company", raw=company.raw)


@router.get("/person/{person_id}/raw", response_model=EntityRawPayloadResponse)
def get_person_raw(
    person_id: str,
    _admin_user: UserContext = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> EntityRawPayloadResponse:
    person = get_person_or_404(session, person_id)
    return EntityRawPayloadResponse(entity_id=person.id, entity_type="person", raw=person.raw)
