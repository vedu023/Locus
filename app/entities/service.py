from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.crustdata.client import CrustdataClient
from app.crustdata.company import company_enrich
from app.crustdata.fields import INVESTOR_COMPANY_FIELDS, RECRUITING_PERSON_FIELDS
from app.crustdata.person import person_enrich
from app.crustdata.types import EnrichRequest
from app.db.models import Company, Person, Signal
from app.lenses.investor import build_investor_signal_summaries
from app.runs.normalization import extract_results, normalize_company, normalize_person
from app.runs.service import upsert_company, upsert_person


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_company_or_404(session: Session, company_id: str) -> Company:
    company = session.scalar(select(Company).where(Company.id == company_id))
    if company is None:
        raise AppError(
            code="NOT_FOUND",
            message="Company not found.",
            status_code=404,
            details={"company_id": company_id},
        )
    return company


def get_person_or_404(session: Session, person_id: str) -> Person:
    person = session.scalar(select(Person).where(Person.id == person_id))
    if person is None:
        raise AppError(
            code="NOT_FOUND",
            message="Person not found.",
            status_code=404,
            details={"person_id": person_id},
        )
    return person


def _extract_single_result(payload: dict[str, Any], entity_type: str) -> dict[str, Any]:
    results = extract_results(payload, entity_type)
    if results:
        return results[0]

    if entity_type == "company" and isinstance(payload.get("company"), dict):
        return payload["company"]
    if entity_type == "person" and isinstance(payload.get("person"), dict):
        return payload["person"]

    keys = {"basic_info", "taxonomy", "headcount", "funding", "locations"}
    if entity_type == "company" and isinstance(payload, dict) and keys & payload.keys():
        return payload
    person_keys = {"basic_profile", "experience", "contact", "social_handles"}
    if entity_type == "person" and isinstance(payload, dict) and person_keys & payload.keys():
        return payload

    raise AppError(
        code="BAD_RESPONSE",
        message="Enrichment response did not include an entity payload.",
        status_code=502,
        details={"entity_type": entity_type},
    )


def _upsert_company_signal(
    *,
    session: Session,
    company: Company,
    signal_type: str,
    title: str,
    description: str | None,
    confidence: float,
    occurred_at: datetime | None,
    raw: dict[str, Any],
) -> Signal:
    signal = session.scalar(
        select(Signal).where(
            Signal.company_id == company.id,
            Signal.signal_type == signal_type,
            Signal.source == "crustdata",
            Signal.title == title,
        )
    )
    if signal is None:
        signal = Signal(
            entity_type="company",
            company_id=company.id,
            location_id=company.hq_location_id,
            signal_type=signal_type,
            source="crustdata",
            title=title,
        )
        session.add(signal)

    signal.location_id = company.hq_location_id
    signal.description = description
    signal.confidence = confidence
    signal.occurred_at = occurred_at
    signal.raw = raw
    session.flush()
    return signal


def enrich_company_entity(
    *,
    session: Session,
    client: CrustdataClient,
    company_id: str,
) -> tuple[Company, int]:
    company = get_company_or_404(session, company_id)

    request = EnrichRequest(fields=list(INVESTOR_COMPANY_FIELDS))
    if company.crustdata_company_id:
        request.ids = [company.crustdata_company_id]
    elif company.primary_domain:
        request.domains = [company.primary_domain]
    else:
        raise AppError(
            code="BAD_INPUT",
            message="Company cannot be enriched because it has no provider identifier or domain.",
            status_code=400,
            details={"company_id": company.id},
        )

    payload = company_enrich(client, request)
    enriched_payload = _extract_single_result(payload, "company")
    company = upsert_company(session, normalize_company(enriched_payload))
    company.last_enriched_at = _utcnow()

    signals = build_investor_signal_summaries(company)
    for signal in signals:
        _upsert_company_signal(
            session=session,
            company=company,
            signal_type=signal.signal_type,
            title=signal.title,
            description=signal.description,
            confidence=signal.confidence,
            occurred_at=signal.occurred_at,
            raw=signal.model_dump(mode="json"),
        )

    session.flush()
    return company, len(signals)


def enrich_person_entity(
    *,
    session: Session,
    client: CrustdataClient,
    person_id: str,
) -> Person:
    person = get_person_or_404(session, person_id)

    request = EnrichRequest(fields=list(RECRUITING_PERSON_FIELDS))
    if person.crustdata_person_id:
        request.ids = [person.crustdata_person_id]
    elif person.professional_network_url:
        request.profile_urls = [person.professional_network_url]
    else:
        raise AppError(
            code="BAD_INPUT",
            message=(
                "Person cannot be enriched because it has no provider identifier "
                "or profile URL."
            ),
            status_code=400,
            details={"person_id": person.id},
        )

    payload = person_enrich(client, request)
    enriched_payload = _extract_single_result(payload, "person")
    person = upsert_person(session, normalize_person(enriched_payload))
    person.last_enriched_at = _utcnow()
    session.flush()
    return person
