from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.crustdata.filters import FilterCondition, FilterGroup, to_safe_contains_pattern
from app.crustdata.types import CompanySearchRequest, PersonSearchRequest
from app.db.models import Company, Location
from app.lenses.scoring import (
    buyer_coverage_fit,
    employee_fit,
    funding_fit,
    funding_recency_fit,
    weighted_average,
)

DEFAULT_BUYER_FIELDS = [
    "basic_profile.name",
    "basic_profile.headline",
    "basic_profile.location",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "experience.employment_details.current.seniority_level",
    "contact.has_business_email",
    "social_handles.professional_network_identifier.profile_url",
]

DEFAULT_BUYER_TITLES = [
    "CEO",
    "Founder",
    "Co-Founder",
    "VP Sales",
    "Head of Sales",
    "Revenue",
]

DEFAULT_BUYER_SENIORITIES = ["cxo", "vp", "director"]


class SalesScoreWeights(BaseModel):
    employee_fit: float = Field(default=0.28, ge=0)
    funding_fit: float = Field(default=0.18, ge=0)
    funding_recency: float = Field(default=0.16, ge=0)
    industry_fit: float = Field(default=0.12, ge=0)
    hq_signal: float = Field(default=0.08, ge=0)
    buyer_coverage: float = Field(default=0.18, ge=0)


class SalesRunInput(BaseModel):
    search: CompanySearchRequest
    top_company_limit: int = Field(default=5, ge=1, le=25)
    buyers_per_company: int = Field(default=3, ge=0, le=25)
    buyer_titles: list[str] = Field(default_factory=lambda: list(DEFAULT_BUYER_TITLES))
    buyer_seniorities: list[str] = Field(default_factory=lambda: list(DEFAULT_BUYER_SENIORITIES))
    buyer_fields: list[str] = Field(
        default_factory=lambda: list(DEFAULT_BUYER_FIELDS),
        min_length=1,
    )
    preferred_industries: list[str] = Field(default_factory=list)
    score_weights: SalesScoreWeights = Field(default_factory=SalesScoreWeights)


class SalesBuyerSummary(BaseModel):
    person_id: str
    name: str
    title: str | None
    seniority: str | None
    headline: str | None
    has_business_email: bool | None
    professional_network_url: str | None


class SalesLocationSummary(BaseModel):
    location_id: str | None
    raw_label: str | None
    latitude: float | None
    longitude: float | None
    status: str
    precision: str | None


class SalesCompanySummary(BaseModel):
    company_id: str
    name: str
    domain: str | None
    industry: str | None
    employee_count: int | None
    funding_total_usd: float | None
    funding_last_round_type: str | None
    funding_last_date: str | None
    location: SalesLocationSummary
    lens_score: float
    buyer_count: int
    buyers: list[SalesBuyerSummary]
    score_breakdown: dict[str, Any]


class SalesRunSummaryStats(BaseModel):
    company_count: int
    mapped_company_count: int
    buyer_count: int
    average_company_score: float
    top_company_score: float | None


class SalesRunSummaryResponse(BaseModel):
    run_id: str
    title: str | None
    summary: SalesRunSummaryStats
    companies: list[SalesCompanySummary]


def build_sales_buyer_search_request(
    *,
    company: Company,
    sales_input: SalesRunInput,
) -> PersonSearchRequest | None:
    if sales_input.buyers_per_company <= 0:
        return None

    company_condition: FilterCondition | None = None
    if company.primary_domain:
        company_condition = FilterCondition(
            field="experience.employment_details.current.company_website_domain",
            type="=",
            value=company.primary_domain,
        )
    elif company.name:
        company_condition = FilterCondition(
            field="experience.employment_details.current.company_name",
            type="=",
            value=company.name,
        )

    if company_condition is None:
        return None

    conditions: list[FilterCondition] = [company_condition]
    if sales_input.buyer_titles:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.title",
                type="(.)",
                value=to_safe_contains_pattern(sales_input.buyer_titles),
            )
        )
    if sales_input.buyer_seniorities:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.seniority_level",
                type="in",
                value=sales_input.buyer_seniorities,
            )
        )

    filters = conditions[0]
    if len(conditions) > 1:
        filters = FilterGroup(op="and", conditions=conditions)

    return PersonSearchRequest(
        fields=sales_input.buyer_fields,
        filters=filters,
        limit=sales_input.buyers_per_company,
    )


def score_sales_company(
    *,
    company: Company,
    sales_input: SalesRunInput,
    buyer_count: int,
    location: Location | None = None,
) -> tuple[float, dict[str, Any]]:
    preferred_industries = {
        industry.strip().lower()
        for industry in sales_input.preferred_industries
        if industry.strip()
    }
    company_industry = (company.industry or "").strip().lower()

    employee_score = employee_fit(company.employee_count)
    funding_score = funding_fit(company.funding_total_usd, company.funding_last_round_amount_usd)
    recency_score = funding_recency_fit(company.funding_last_date)
    industry_score = 0.6
    if preferred_industries:
        industry_score = 1.0 if company_industry in preferred_industries else 0.2
    hq_score = 1.0 if company.hq_location_id else 0.3
    buyer_score = buyer_coverage_fit(buyer_count, sales_input.buyers_per_company)

    weights = sales_input.score_weights
    weighted_inputs = {
        "employee_fit": (employee_score, weights.employee_fit),
        "funding_fit": (funding_score, weights.funding_fit),
        "funding_recency": (recency_score, weights.funding_recency),
        "industry_fit": (industry_score, weights.industry_fit),
        "hq_signal": (hq_score, weights.hq_signal),
        "buyer_coverage": (
            buyer_score,
            weights.buyer_coverage if sales_input.buyers_per_company > 0 else 0.0,
        ),
    }
    score = round(weighted_average(weighted_inputs) * 100, 2)

    return score, {
        "employee_fit": round(employee_score, 3),
        "funding_fit": round(funding_score, 3),
        "funding_recency": round(recency_score, 3),
        "industry_fit": round(industry_score, 3),
        "hq_signal": round(hq_score, 3),
        "buyer_coverage": round(buyer_score, 3),
        "preferred_industries": sorted(preferred_industries),
        "buyer_target": sales_input.buyers_per_company,
        "company_location_status": location.geocode_status if location else "missing",
        "company_location_precision": location.geocode_precision if location else None,
    }
