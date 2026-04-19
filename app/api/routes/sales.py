from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_session
from app.core.auth import UserContext, get_current_user
from app.core.errors import AppError
from app.db.models import Person, SearchRunEntity
from app.lenses.sales import (
    SalesBuyerSummary,
    SalesCompanySummary,
    SalesLocationSummary,
    SalesRunSummaryResponse,
    SalesRunSummaryStats,
)
from app.runs.service import get_search_run

router = APIRouter(prefix="/runs", tags=["sales"])


@router.get("/{run_id}/sales-summary", response_model=SalesRunSummaryResponse)
def get_sales_summary(
    run_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SalesRunSummaryResponse:
    run = get_search_run(session=session, current_user=current_user, run_id=run_id)
    if run.lens != "sales":
        raise AppError(
            code="BAD_INPUT",
            message="Sales summary is only available for sales runs.",
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

    buyer_ids: set[str] = set()
    for entity in entities:
        raw_ids = entity.score_breakdown.get("buyer_person_ids", [])
        if isinstance(raw_ids, list):
            buyer_ids.update(str(raw_id) for raw_id in raw_ids)

    buyers_by_id: dict[str, Person] = {}
    if buyer_ids:
        buyers = session.scalars(select(Person).where(Person.id.in_(sorted(buyer_ids)))).all()
        buyers_by_id = {buyer.id: buyer for buyer in buyers}

    company_items: list[SalesCompanySummary] = []
    total_buyers = int(run.result_counts.get("buyers", 0))
    mapped_companies = sum(
        1
        for entity in entities
        if entity.location is not None and entity.location.geocode_status == "mapped"
    )
    total_score = sum(entity.lens_score for entity in entities)

    for entity in entities[:limit]:
        if entity.company is None:
            continue

        raw_ids = entity.score_breakdown.get("buyer_person_ids", [])
        buyer_people = [
            buyers_by_id[buyer_id]
            for buyer_id in raw_ids
            if isinstance(buyer_id, str) and buyer_id in buyers_by_id
        ]
        company_items.append(
            SalesCompanySummary(
                company_id=entity.company.id,
                name=entity.company.name,
                domain=entity.company.primary_domain,
                industry=entity.company.industry,
                employee_count=entity.company.employee_count,
                funding_total_usd=entity.company.funding_total_usd,
                funding_last_round_type=entity.company.funding_last_round_type,
                funding_last_date=(
                    entity.company.funding_last_date.isoformat()
                    if entity.company.funding_last_date is not None
                    else None
                ),
                location=SalesLocationSummary(
                    location_id=entity.location_id,
                    raw_label=entity.location.raw_label if entity.location else None,
                    latitude=entity.location.latitude if entity.location else None,
                    longitude=entity.location.longitude if entity.location else None,
                    status=entity.location.geocode_status if entity.location else "missing",
                    precision=entity.location.geocode_precision if entity.location else None,
                ),
                lens_score=entity.lens_score,
                buyer_count=len(buyer_people),
                buyers=[
                    SalesBuyerSummary(
                        person_id=buyer.id,
                        name=buyer.name,
                        title=buyer.current_title,
                        seniority=buyer.seniority_level,
                        headline=buyer.headline,
                        has_business_email=buyer.has_business_email,
                        professional_network_url=buyer.professional_network_url,
                    )
                    for buyer in buyer_people
                ],
                score_breakdown=entity.score_breakdown,
            )
        )

    average_score = 0.0
    if entities:
        average_score = round(total_score / len(entities), 2)

    return SalesRunSummaryResponse(
        run_id=run.id,
        title=run.title,
        summary=SalesRunSummaryStats(
            company_count=len(entities),
            mapped_company_count=mapped_companies,
            buyer_count=total_buyers,
            average_company_score=average_score,
            top_company_score=company_items[0].lens_score if company_items else None,
        ),
        companies=company_items,
    )
