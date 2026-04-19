from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import UserContext
from app.core.errors import AppError
from app.crustdata.client import CrustdataClient
from app.crustdata.company import company_search
from app.crustdata.person import person_search
from app.db.models import Company, Location, Person, SearchRun, SearchRunEntity, User
from app.runs.normalization import (
    NormalizedCompany,
    NormalizedLocation,
    NormalizedPerson,
    extract_results,
    normalize_company,
    normalize_person,
)
from app.runs.schemas import CreateRunRequest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_user(session: Session, current_user: UserContext) -> User:
    user = session.scalar(select(User).where(User.auth_provider_id == current_user.user_id))
    if user is not None:
        if user.email != current_user.email:
            user.email = current_user.email
        return user

    user = User(auth_provider_id=current_user.user_id, email=current_user.email)
    session.add(user)
    session.flush()
    return user


def _get_or_create_location(
    session: Session, location: NormalizedLocation | None
) -> Location | None:
    if location is None:
        return None

    existing = session.scalar(
        select(Location).where(Location.location_key == location.location_key)
    )
    if existing is not None:
        existing.raw_label = location.raw_label
        existing.city = location.city
        existing.region = location.region
        existing.country = location.country
        existing.country_code = location.country_code
        return existing

    created = Location(
        location_key=location.location_key,
        raw_label=location.raw_label,
        city=location.city,
        region=location.region,
        country=location.country,
        country_code=location.country_code,
    )
    session.add(created)
    session.flush()
    return created


def _find_company(session: Session, normalized: NormalizedCompany) -> Company | None:
    if normalized.crustdata_company_id:
        company = session.scalar(
            select(Company).where(Company.crustdata_company_id == normalized.crustdata_company_id)
        )
        if company is not None:
            return company

    if normalized.primary_domain:
        return session.scalar(
            select(Company).where(Company.primary_domain == normalized.primary_domain)
        )

    return None


def _find_person(session: Session, normalized: NormalizedPerson) -> Person | None:
    if normalized.crustdata_person_id:
        person = session.scalar(
            select(Person).where(Person.crustdata_person_id == normalized.crustdata_person_id)
        )
        if person is not None:
            return person

    if normalized.professional_network_url:
        return session.scalar(
            select(Person).where(
                Person.professional_network_url == normalized.professional_network_url
            )
        )

    return None


def upsert_company(session: Session, normalized: NormalizedCompany) -> Company:
    location = _get_or_create_location(session, normalized.location)
    company = _find_company(session, normalized)

    if company is None:
        company = Company(name=normalized.name)
        session.add(company)

    company.crustdata_company_id = normalized.crustdata_company_id
    company.name = normalized.name
    company.primary_domain = normalized.primary_domain
    company.website = normalized.website
    company.professional_network_url = normalized.professional_network_url
    company.industry = normalized.industry
    company.company_type = normalized.company_type
    company.year_founded = normalized.year_founded
    company.employee_count = normalized.employee_count
    company.employee_count_range = normalized.employee_count_range
    company.funding_total_usd = normalized.funding_total_usd
    company.funding_last_round_type = normalized.funding_last_round_type
    company.funding_last_round_amount_usd = normalized.funding_last_round_amount_usd
    company.funding_last_date = normalized.funding_last_date
    company.hq_location = location
    company.raw = normalized.raw
    company.last_seen_at = _utcnow()
    session.flush()
    return company


def upsert_person(session: Session, normalized: NormalizedPerson) -> Person:
    location = _get_or_create_location(session, normalized.location)
    person = _find_person(session, normalized)

    if person is None:
        person = Person(name=normalized.name)
        session.add(person)

    company = None
    if normalized.current_company_domain or normalized.current_company_name:
        if normalized.current_company_domain:
            company = session.scalar(
                select(Company).where(Company.primary_domain == normalized.current_company_domain)
            )
        if company is None and normalized.current_company_name:
            company = session.scalar(
                select(Company).where(Company.name == normalized.current_company_name)
            )

    person.crustdata_person_id = normalized.crustdata_person_id
    person.name = normalized.name
    person.professional_network_url = normalized.professional_network_url
    person.headline = normalized.headline
    person.current_title = normalized.current_title
    person.current_company_name = normalized.current_company_name
    person.current_company_domain = normalized.current_company_domain
    person.current_company = company
    person.seniority_level = normalized.seniority_level
    person.function_category = normalized.function_category
    person.location = location
    person.has_business_email = normalized.has_business_email
    person.has_personal_email = normalized.has_personal_email
    person.has_phone_number = normalized.has_phone_number
    person.raw = normalized.raw
    person.last_seen_at = _utcnow()
    session.flush()
    return person


def _calculate_result_counts(
    *,
    entity_type: str,
    entities: Iterable[SearchRunEntity],
) -> dict[str, int | str]:
    entity_list = list(entities)
    location_ids = {entity.location_id for entity in entity_list if entity.location_id}
    unmapped = sum(1 for entity in entity_list if entity.location_id is None)
    return {
        "companies": sum(1 for entity in entity_list if entity.entity_type == "company"),
        "people": sum(1 for entity in entity_list if entity.entity_type == "person"),
        "locations": len(location_ids),
        "unmapped": unmapped,
        "primary_entity_type": entity_type,
    }


def _serialize_filters(request: CreateRunRequest) -> dict:
    search = request.input.search
    dumped = search.model_dump(exclude_none=True)
    filters = dumped.get("filters")
    return filters if isinstance(filters, dict) else {}


def _build_run(request: CreateRunRequest, user: User) -> SearchRun:
    return SearchRun(
        user_id=user.id,
        lens=request.lens,
        title=request.title,
        input_payload=request.model_dump(mode="json"),
        normalized_filters=_serialize_filters(request),
        status="running",
        result_counts={},
        cost_estimate={},
    )


def create_search_run(
    *,
    session: Session,
    client: CrustdataClient,
    current_user: UserContext,
    request: CreateRunRequest,
) -> SearchRun:
    user = get_or_create_user(session, current_user)
    run = _build_run(request, user)
    session.add(run)
    session.flush()
    run_id = run.id

    try:
        if request.lens in {"sales", "investor"}:
            payload = company_search(client, request.input.search)
            raw_results = extract_results(payload, "company")
            entities = []
            for rank, item in enumerate(raw_results, start=1):
                company = upsert_company(session, normalize_company(item))
                entity = SearchRunEntity(
                    run_id=run.id,
                    entity_type="company",
                    company_id=company.id,
                    location_id=company.hq_location_id,
                    rank=rank,
                    lens_score=0.0,
                    score_breakdown={},
                )
                session.add(entity)
                entities.append(entity)
            primary_entity_type = "company"
        else:
            payload = person_search(client, request.input.search)
            raw_results = extract_results(payload, "person")
            entities = []
            for rank, item in enumerate(raw_results, start=1):
                person = upsert_person(session, normalize_person(item))
                entity = SearchRunEntity(
                    run_id=run.id,
                    entity_type="person",
                    person_id=person.id,
                    location_id=person.location_id,
                    rank=rank,
                    lens_score=0.0,
                    score_breakdown={},
                )
                session.add(entity)
                entities.append(entity)
            primary_entity_type = "person"

        run.result_counts = _calculate_result_counts(
            entity_type=primary_entity_type,
            entities=entities,
        )
        run.status = "complete"
        run.completed_at = _utcnow()
        session.commit()
    except Exception as exc:
        session.rollback()
        user = get_or_create_user(session, current_user)
        failed_run = SearchRun(
            id=run_id,
            user_id=user.id,
            lens=request.lens,
            title=request.title,
            input_payload=request.model_dump(mode="json"),
            normalized_filters=_serialize_filters(request),
            status="failed",
            error_message=str(exc),
            result_counts={},
            cost_estimate={},
            created_at=_utcnow(),
            completed_at=_utcnow(),
        )
        failed_run.status = "failed"
        session.add(failed_run)
        session.commit()
        if isinstance(exc, AppError):
            raise
        raise

    session.refresh(run)
    return run


def get_search_run(*, session: Session, current_user: UserContext, run_id: str) -> SearchRun:
    user = get_or_create_user(session, current_user)
    run = session.scalar(
        select(SearchRun).where(SearchRun.id == run_id, SearchRun.user_id == user.id)
    )
    if run is None:
        raise AppError(
            code="NOT_FOUND",
            message="Search run not found.",
            status_code=404,
            details={"run_id": run_id},
        )
    return run
