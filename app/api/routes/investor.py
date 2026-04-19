from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_session
from app.core.auth import UserContext, get_current_user
from app.core.errors import AppError
from app.db.models import Person, SearchRunEntity
from app.lenses.investor import (
    InvestorCompanySummary,
    InvestorFounderSummary,
    InvestorLocationSummary,
    InvestorRunSummaryResponse,
    InvestorRunSummaryStats,
    build_investor_signal_summaries,
)
from app.runs.service import get_search_run

router = APIRouter(prefix="/runs", tags=["investor"])


@router.get("/{run_id}/investor-summary", response_model=InvestorRunSummaryResponse)
def get_investor_summary(
    run_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> InvestorRunSummaryResponse:
    run = get_search_run(session=session, current_user=current_user, run_id=run_id)
    if run.lens != "investor":
        raise AppError(
            code="BAD_INPUT",
            message="Investor summary is only available for investor runs.",
            status_code=400,
        )

    entities = session.scalars(
        select(SearchRunEntity)
        .where(
            SearchRunEntity.run_id == run.id,
            SearchRunEntity.entity_type == "company",
        )
        .options(
            joinedload(SearchRunEntity.company),
            joinedload(SearchRunEntity.location),
        )
        .order_by(SearchRunEntity.lens_score.desc(), SearchRunEntity.rank.asc().nullslast())
    ).all()

    founder_ids: set[str] = set()
    for entity in entities:
        raw_ids = entity.score_breakdown.get("founder_person_ids", [])
        if isinstance(raw_ids, list):
            founder_ids.update(str(raw_id) for raw_id in raw_ids)

    founders_by_id: dict[str, Person] = {}
    if founder_ids:
        founders = session.scalars(select(Person).where(Person.id.in_(sorted(founder_ids)))).all()
        founders_by_id = {founder.id: founder for founder in founders}

    company_items: list[InvestorCompanySummary] = []
    total_score = sum(entity.lens_score for entity in entities)
    total_signals = 0
    mapped_companies = sum(
        1
        for entity in entities
        if entity.location is not None and entity.location.geocode_status == "mapped"
    )

    for entity in entities[:limit]:
        if entity.company is None:
            continue

        raw_ids = entity.score_breakdown.get("founder_person_ids", [])
        founder_people = [
            founders_by_id[founder_id]
            for founder_id in raw_ids
            if isinstance(founder_id, str) and founder_id in founders_by_id
        ]
        signals = build_investor_signal_summaries(entity.company)
        total_signals += len(signals)

        markets = entity.score_breakdown.get("markets", [])
        categories = entity.score_breakdown.get("categories", [])
        company_items.append(
            InvestorCompanySummary(
                company_id=entity.company.id,
                name=entity.company.name,
                domain=entity.company.primary_domain,
                website=entity.company.website,
                industry=entity.company.industry,
                markets=markets if isinstance(markets, list) else [],
                categories=categories if isinstance(categories, list) else [],
                employee_count=entity.company.employee_count,
                funding_total_usd=entity.company.funding_total_usd,
                funding_last_round_type=entity.company.funding_last_round_type,
                funding_last_date=(
                    entity.company.funding_last_date.isoformat()
                    if entity.company.funding_last_date is not None
                    else None
                ),
                location=InvestorLocationSummary(
                    location_id=entity.location_id,
                    raw_label=entity.location.raw_label if entity.location else None,
                    latitude=entity.location.latitude if entity.location else None,
                    longitude=entity.location.longitude if entity.location else None,
                    status=entity.location.geocode_status if entity.location else "missing",
                    precision=entity.location.geocode_precision if entity.location else None,
                ),
                lens_score=entity.lens_score,
                founder_count=len(founder_people),
                founders=[
                    InvestorFounderSummary(
                        person_id=founder.id,
                        name=founder.name,
                        title=founder.current_title,
                        headline=founder.headline,
                        current_company_name=founder.current_company_name,
                        current_company_domain=founder.current_company_domain,
                        professional_network_url=founder.professional_network_url,
                    )
                    for founder in founder_people
                ],
                signals=signals,
                score_breakdown=entity.score_breakdown,
            )
        )

    average_score = 0.0
    if entities:
        average_score = round(total_score / len(entities), 2)

    return InvestorRunSummaryResponse(
        run_id=run.id,
        title=run.title,
        summary=InvestorRunSummaryStats(
            company_count=len(entities),
            mapped_company_count=mapped_companies,
            founder_count=int(run.result_counts.get("founders", 0)),
            signal_count=int(run.result_counts.get("signals", total_signals)),
            average_company_score=average_score,
            top_company_score=company_items[0].lens_score if company_items else None,
        ),
        companies=company_items,
    )
