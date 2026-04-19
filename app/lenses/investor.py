from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.crustdata.fields import INVESTOR_COMPANY_FIELDS, INVESTOR_FOUNDER_FIELDS
from app.crustdata.filters import FilterCondition, FilterGroup, to_safe_contains_pattern
from app.crustdata.types import CompanySearchRequest, PersonSearchRequest
from app.db.models import Company, Location
from app.lenses.scoring import (
    buyer_coverage_fit,
    funding_fit,
    funding_recency_fit,
    weighted_average,
)

DEFAULT_FOUNDER_TITLES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Chief Executive Officer",
    "CTO",
    "Chief Technology Officer",
]

DEFAULT_FOUNDER_SENIORITIES = ["cxo", "vp", "director"]


class InvestorScoreWeights(BaseModel):
    funding_fit: float = Field(default=0.16, ge=0)
    funding_recency: float = Field(default=0.16, ge=0)
    hiring_growth: float = Field(default=0.18, ge=0)
    follower_growth: float = Field(default=0.14, ge=0)
    headcount_momentum: float = Field(default=0.16, ge=0)
    founder_coverage: float = Field(default=0.12, ge=0)
    market_fit: float = Field(default=0.08, ge=0)


class InvestorRunInput(BaseModel):
    search: CompanySearchRequest
    target_markets: list[str] = Field(default_factory=list)
    target_categories: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    min_headcount: int | None = Field(default=None, ge=1)
    max_headcount: int | None = Field(default=None, ge=1)
    min_openings_growth_percent: float | None = None
    min_follower_growth_percent: float | None = None
    top_company_limit: int = Field(default=5, ge=1, le=25)
    founders_per_company: int = Field(default=3, ge=0, le=25)
    founder_titles: list[str] = Field(default_factory=lambda: list(DEFAULT_FOUNDER_TITLES))
    founder_seniorities: list[str] = Field(
        default_factory=lambda: list(DEFAULT_FOUNDER_SENIORITIES)
    )
    company_fields: list[str] = Field(
        default_factory=lambda: list(INVESTOR_COMPANY_FIELDS),
        min_length=1,
    )
    founder_fields: list[str] = Field(
        default_factory=lambda: list(INVESTOR_FOUNDER_FIELDS),
        min_length=1,
    )
    score_weights: InvestorScoreWeights = Field(default_factory=InvestorScoreWeights)


class InvestorFounderSummary(BaseModel):
    person_id: str
    name: str
    title: str | None
    headline: str | None
    current_company_name: str | None
    current_company_domain: str | None
    professional_network_url: str | None


class InvestorSignalSummary(BaseModel):
    signal_type: str
    title: str
    description: str | None
    confidence: float
    occurred_at: datetime | None


class InvestorLocationSummary(BaseModel):
    location_id: str | None
    raw_label: str | None
    latitude: float | None
    longitude: float | None
    status: str
    precision: str | None


class InvestorCompanySummary(BaseModel):
    company_id: str
    name: str
    domain: str | None
    website: str | None
    industry: str | None
    markets: list[str]
    categories: list[str]
    employee_count: int | None
    funding_total_usd: float | None
    funding_last_round_type: str | None
    funding_last_date: str | None
    location: InvestorLocationSummary
    lens_score: float
    founder_count: int
    founders: list[InvestorFounderSummary]
    signals: list[InvestorSignalSummary]
    score_breakdown: dict[str, Any]


class InvestorRunSummaryStats(BaseModel):
    company_count: int
    mapped_company_count: int
    founder_count: int
    signal_count: int
    average_company_score: float
    top_company_score: float | None


class InvestorRunSummaryResponse(BaseModel):
    run_id: str
    title: str | None
    summary: InvestorRunSummaryStats
    companies: list[InvestorCompanySummary]


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _merge_filters(
    base_filters: FilterCondition | FilterGroup | None,
    conditions: list[FilterCondition],
) -> FilterCondition | FilterGroup | None:
    nodes: list[FilterCondition | FilterGroup] = []
    if base_filters is not None:
        nodes.append(base_filters)
    nodes.extend(conditions)

    if not nodes:
        return None
    if len(nodes) == 1:
        return nodes[0]
    return FilterGroup(op="and", conditions=nodes)


def _raw_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _raw_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _raw_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _first_numeric(*values: object) -> float | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "").replace(",", "")
            if not cleaned:
                continue
            try:
                return float(cleaned)
            except ValueError:
                continue
    return None


def _growth_fit(value: float | None) -> float:
    if value is None:
        return 0.35
    if value >= 100:
        return 1.0
    if value >= 50:
        return 0.85
    if value >= 20:
        return 0.65
    if value > 0:
        return 0.45
    if value >= -10:
        return 0.3
    return 0.15


def _headcount_momentum(company: Company) -> tuple[float, float | None]:
    raw = _raw_dict(company.raw)
    roles = _raw_dict(raw.get("roles"))
    growth = _first_numeric(roles.get("growth_6m"), roles.get("growth_yoy"))
    if growth is not None:
        return _growth_fit(growth), growth

    employee_count = company.employee_count
    if employee_count is None:
        return 0.3, None
    if 10 <= employee_count <= 250:
        return 0.7, None
    if 251 <= employee_count <= 1000:
        return 0.55, None
    return 0.35, None


def _company_taxonomy(company: Company) -> tuple[list[str], list[str]]:
    raw = _raw_dict(company.raw)
    basic_info = _raw_dict(raw.get("basic_info"))
    taxonomy = _raw_dict(raw.get("taxonomy"))
    return (
        _raw_string_list(basic_info.get("markets")),
        _raw_string_list(taxonomy.get("categories")),
    )


def _market_fit(
    company: Company,
    investor_input: InvestorRunInput,
) -> tuple[float, dict[str, list[str]]]:
    markets, categories = _company_taxonomy(company)
    industry = _normalize_text(company.industry)

    target_markets = {
        _normalize_text(value) for value in investor_input.target_markets if value.strip()
    }
    target_categories = {
        _normalize_text(value) for value in investor_input.target_categories if value.strip()
    }
    target_industries = {
        _normalize_text(value) for value in investor_input.target_industries if value.strip()
    }

    if not target_markets and not target_categories and not target_industries:
        return 0.55, {"markets": markets, "categories": categories}

    normalized_markets = {_normalize_text(value) for value in markets}
    normalized_categories = {_normalize_text(value) for value in categories}

    matched = (
        bool(target_markets & normalized_markets)
        or bool(target_categories & normalized_categories)
        or (industry != "" and industry in target_industries)
    )
    return (1.0 if matched else 0.2), {"markets": markets, "categories": categories}


def build_investor_company_search_request(investor_input: InvestorRunInput) -> CompanySearchRequest:
    if (
        investor_input.min_headcount is not None
        and investor_input.max_headcount is not None
        and investor_input.min_headcount > investor_input.max_headcount
    ):
        raise AppError(
            code="BAD_INPUT",
            message="min_headcount cannot be greater than max_headcount.",
            status_code=400,
        )

    conditions: list[FilterCondition] = []
    if investor_input.target_markets:
        conditions.append(
            FilterCondition(
                field="basic_info.markets",
                type="(.)",
                value=to_safe_contains_pattern(investor_input.target_markets),
            )
        )
    if investor_input.target_categories:
        conditions.append(
            FilterCondition(
                field="taxonomy.categories",
                type="(.)",
                value=to_safe_contains_pattern(investor_input.target_categories),
            )
        )
    if investor_input.target_industries:
        conditions.append(
            FilterCondition(
                field="taxonomy.professional_network_industry",
                type="(.)",
                value=to_safe_contains_pattern(investor_input.target_industries),
            )
        )
    if investor_input.min_headcount is not None:
        conditions.append(
            FilterCondition(field="headcount.total", type="=>", value=investor_input.min_headcount)
        )
    if investor_input.max_headcount is not None:
        conditions.append(
            FilterCondition(field="headcount.total", type="=<", value=investor_input.max_headcount)
        )
    if investor_input.min_openings_growth_percent is not None:
        conditions.append(
            FilterCondition(
                field="hiring.openings_growth_percent",
                type="=>",
                value=investor_input.min_openings_growth_percent,
            )
        )
    if investor_input.min_follower_growth_percent is not None:
        conditions.append(
            FilterCondition(
                field="followers.six_months_growth_percent",
                type="=>",
                value=investor_input.min_follower_growth_percent,
            )
        )

    search = investor_input.search
    return CompanySearchRequest(
        fields=investor_input.company_fields or search.fields,
        filters=_merge_filters(search.filters, conditions),
        limit=search.limit,
        cursor=search.cursor,
    )


def build_investor_founder_search_request(
    *,
    company: Company,
    investor_input: InvestorRunInput,
) -> PersonSearchRequest | None:
    if investor_input.founders_per_company <= 0:
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
    if investor_input.founder_titles:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.title",
                type="(.)",
                value=to_safe_contains_pattern(investor_input.founder_titles),
            )
        )
    if investor_input.founder_seniorities:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.seniority_level",
                type="in",
                value=investor_input.founder_seniorities,
            )
        )

    filters = conditions[0]
    if len(conditions) > 1:
        filters = FilterGroup(op="and", conditions=conditions)

    return PersonSearchRequest(
        fields=investor_input.founder_fields,
        filters=filters,
        limit=investor_input.founders_per_company,
    )


def score_investor_company(
    *,
    company: Company,
    investor_input: InvestorRunInput,
    founder_count: int,
    location: Location | None = None,
) -> tuple[float, dict[str, Any]]:
    raw = _raw_dict(company.raw)
    hiring = _raw_dict(raw.get("hiring"))
    followers = _raw_dict(raw.get("followers"))

    openings_growth = _first_numeric(hiring.get("openings_growth_percent"))
    follower_growth = _first_numeric(followers.get("six_months_growth_percent"))
    headcount_score, headcount_growth = _headcount_momentum(company)
    market_score, taxonomy = _market_fit(company, investor_input)
    founder_score = buyer_coverage_fit(founder_count, investor_input.founders_per_company)

    weights = investor_input.score_weights
    weighted_inputs = {
        "funding_fit": (
            funding_fit(company.funding_total_usd, company.funding_last_round_amount_usd),
            weights.funding_fit,
        ),
        "funding_recency": (
            funding_recency_fit(company.funding_last_date),
            weights.funding_recency,
        ),
        "hiring_growth": (_growth_fit(openings_growth), weights.hiring_growth),
        "follower_growth": (_growth_fit(follower_growth), weights.follower_growth),
        "headcount_momentum": (headcount_score, weights.headcount_momentum),
        "founder_coverage": (
            founder_score,
            weights.founder_coverage if investor_input.founders_per_company > 0 else 0.0,
        ),
        "market_fit": (market_score, weights.market_fit),
    }
    score = round(weighted_average(weighted_inputs) * 100, 2)

    return score, {
        "funding_fit": round(weighted_inputs["funding_fit"][0], 3),
        "funding_recency": round(weighted_inputs["funding_recency"][0], 3),
        "hiring_growth": round(weighted_inputs["hiring_growth"][0], 3),
        "follower_growth": round(weighted_inputs["follower_growth"][0], 3),
        "headcount_momentum": round(headcount_score, 3),
        "founder_coverage": round(founder_score, 3),
        "market_fit": round(market_score, 3),
        "openings_growth_percent": openings_growth,
        "follower_growth_percent": follower_growth,
        "headcount_growth_percent": headcount_growth,
        "markets": taxonomy["markets"],
        "categories": taxonomy["categories"],
        "founder_target": investor_input.founders_per_company,
        "company_location_status": location.geocode_status if location else "missing",
        "company_location_precision": location.geocode_precision if location else None,
    }


def build_investor_signal_summaries(company: Company) -> list[InvestorSignalSummary]:
    raw = _raw_dict(company.raw)
    hiring = _raw_dict(raw.get("hiring"))
    roles = _raw_dict(raw.get("roles"))

    signals: list[InvestorSignalSummary] = []
    if (
        company.funding_total_usd is not None
        or company.funding_last_round_amount_usd is not None
        or company.funding_last_date is not None
    ):
        description_parts: list[str] = []
        if company.funding_last_round_amount_usd is not None:
            description_parts.append(
                f"Last round ${company.funding_last_round_amount_usd:,.0f}"
            )
        if company.funding_total_usd is not None:
            description_parts.append(f"Total funding ${company.funding_total_usd:,.0f}")
        occurred_at = None
        if company.funding_last_date is not None:
            occurred_at = datetime.combine(
                company.funding_last_date,
                time.min,
                tzinfo=timezone.utc,
            )
            description_parts.append(f"Last raised on {company.funding_last_date.isoformat()}")
        signals.append(
            InvestorSignalSummary(
                signal_type="funding",
                title=(
                    f"{company.funding_last_round_type.title()} funding"
                    if company.funding_last_round_type
                    else "Funding activity"
                ),
                description=" | ".join(description_parts) if description_parts else None,
                confidence=0.9 if occurred_at is not None else 0.75,
                occurred_at=occurred_at,
            )
        )

    openings_count = _first_numeric(hiring.get("openings_count"))
    openings_growth = _first_numeric(hiring.get("openings_growth_percent"))
    if openings_count is not None or openings_growth is not None:
        description_parts = []
        if openings_count is not None:
            description_parts.append(f"{int(openings_count)} open roles")
        if openings_growth is not None:
            description_parts.append(f"{openings_growth:.1f}% openings growth")
        signals.append(
            InvestorSignalSummary(
                signal_type="hiring",
                title="Hiring momentum",
                description=" | ".join(description_parts) if description_parts else None,
                confidence=0.85 if openings_growth is not None and openings_growth > 0 else 0.65,
                occurred_at=None,
            )
        )

    growth_6m = _first_numeric(roles.get("growth_6m"))
    growth_yoy = _first_numeric(roles.get("growth_yoy"))
    if company.employee_count is not None or growth_6m is not None or growth_yoy is not None:
        description_parts = []
        if company.employee_count is not None:
            description_parts.append(f"{company.employee_count} employees")
        if growth_6m is not None:
            description_parts.append(f"{growth_6m:.1f}% headcount growth in 6m")
        if growth_yoy is not None:
            description_parts.append(f"{growth_yoy:.1f}% headcount growth YoY")
        signals.append(
            InvestorSignalSummary(
                signal_type="headcount",
                title="Headcount signal",
                description=" | ".join(description_parts) if description_parts else None,
                confidence=0.8 if growth_6m is not None or growth_yoy is not None else 0.6,
                occurred_at=None,
            )
        )

    return signals
