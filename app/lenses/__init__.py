"""Lens-specific backend logic for Locus."""

from app.lenses.recruiting import (
    RecruitingCandidateSummary,
    RecruitingLocationAggregate,
    RecruitingRunInput,
    RecruitingRunSummaryResponse,
    RecruitingRunSummaryStats,
    build_recruiting_search_request,
    score_recruiting_person,
)
from app.lenses.sales import (
    SalesCompanySummary,
    SalesRunInput,
    SalesRunSummaryResponse,
    SalesRunSummaryStats,
    build_sales_buyer_search_request,
    score_sales_company,
)

__all__ = [
    "RecruitingCandidateSummary",
    "RecruitingLocationAggregate",
    "RecruitingRunInput",
    "RecruitingRunSummaryResponse",
    "RecruitingRunSummaryStats",
    "SalesCompanySummary",
    "SalesRunInput",
    "SalesRunSummaryResponse",
    "SalesRunSummaryStats",
    "build_recruiting_search_request",
    "build_sales_buyer_search_request",
    "score_recruiting_person",
    "score_sales_company",
]
