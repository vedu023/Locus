from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_session
from app.core.auth import UserContext, get_current_user
from app.core.errors import AppError
from app.db.models import SearchRunEntity
from app.lenses.recruiting import (
    RecruitingCandidateSummary,
    RecruitingLocationAggregate,
    RecruitingRunSummaryResponse,
    RecruitingRunSummaryStats,
)
from app.runs.service import get_search_run

router = APIRouter(prefix="/runs", tags=["recruiting"])


@dataclass
class _LocationAccumulator:
    location_id: str | None
    raw_label: str | None
    latitude: float | None
    longitude: float | None
    status: str
    precision: str | None
    people_count: int = 0
    employers: set[str] = field(default_factory=set)

    def to_model(self) -> RecruitingLocationAggregate:
        employers = sorted(self.employers)
        return RecruitingLocationAggregate(
            location_id=self.location_id,
            raw_label=self.raw_label,
            latitude=self.latitude,
            longitude=self.longitude,
            status=self.status,
            precision=self.precision,
            people_count=self.people_count,
            employer_count=len(employers),
            employers=employers[:5],
        )


@router.get("/{run_id}/recruiting-summary", response_model=RecruitingRunSummaryResponse)
def get_recruiting_summary(
    run_id: str,
    limit: int | None = Query(default=None, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RecruitingRunSummaryResponse:
    run = get_search_run(session=session, current_user=current_user, run_id=run_id)
    if run.lens != "recruiting":
        raise AppError(
            code="BAD_INPUT",
            message="Recruiting summary is only available for recruiting runs.",
            status_code=400,
        )

    effective_limit = limit
    if effective_limit is None:
        raw_input = run.input_payload.get("input", {})
        if not isinstance(raw_input, dict):
            raw_input = {}
        raw_default = raw_input.get("top_candidate_limit")
        if isinstance(raw_default, int) and raw_default > 0:
            effective_limit = raw_default
        else:
            effective_limit = 25

    entities = session.scalars(
        select(SearchRunEntity)
        .where(
            SearchRunEntity.run_id == run.id,
            SearchRunEntity.entity_type == "person",
        )
        .options(
            joinedload(SearchRunEntity.person),
            joinedload(SearchRunEntity.location),
        )
        .order_by(SearchRunEntity.lens_score.desc(), SearchRunEntity.rank.asc().nullslast())
    ).all()

    location_accumulators: dict[str | None, _LocationAccumulator] = {}
    employer_keys: set[str] = set()
    for entity in entities:
        person = entity.person
        if person is None:
            continue

        employer_key = person.current_company_domain or person.current_company_name
        if employer_key:
            employer_keys.add(employer_key)

        location = entity.location
        key = entity.location_id
        accumulator = location_accumulators.setdefault(
            key,
            _LocationAccumulator(
                location_id=entity.location_id,
                raw_label=location.raw_label if location else None,
                latitude=location.latitude if location else None,
                longitude=location.longitude if location else None,
                status=location.geocode_status if location else "missing",
                precision=location.geocode_precision if location else None,
            ),
        )
        accumulator.people_count += 1
        if employer_key:
            accumulator.employers.add(employer_key)

    candidates: list[RecruitingCandidateSummary] = []
    for entity in entities[:effective_limit]:
        if entity.person is None:
            continue
        person = entity.person
        location = entity.location
        candidates.append(
            RecruitingCandidateSummary(
                person_id=person.id,
                name=person.name,
                title=person.current_title,
                seniority=person.seniority_level,
                function_category=person.function_category,
                current_company_name=person.current_company_name,
                current_company_domain=person.current_company_domain,
                headline=person.headline,
                has_business_email=person.has_business_email,
                has_phone_number=person.has_phone_number,
                lens_score=entity.lens_score,
                location={
                    "location_id": entity.location_id,
                    "raw_label": location.raw_label if location else None,
                    "latitude": location.latitude if location else None,
                    "longitude": location.longitude if location else None,
                    "status": location.geocode_status if location else "missing",
                    "precision": location.geocode_precision if location else None,
                },
                score_breakdown=entity.score_breakdown,
            )
        )

    mapped_people = sum(
        1
        for entity in entities
        if entity.location is not None and entity.location.geocode_status == "mapped"
    )
    average_score = 0.0
    if entities:
        average_score = round(sum(entity.lens_score for entity in entities) / len(entities), 2)

    return RecruitingRunSummaryResponse(
        run_id=run.id,
        title=run.title,
        summary=RecruitingRunSummaryStats(
            people_count=len(entities),
            mapped_people_count=mapped_people,
            employer_count=len(employer_keys),
            average_candidate_score=average_score,
            top_candidate_score=candidates[0].lens_score if candidates else None,
        ),
        candidates=candidates,
        locations=sorted(
            (accumulator.to_model() for accumulator in location_accumulators.values()),
            key=lambda item: (-item.people_count, item.raw_label or ""),
        ),
    )
