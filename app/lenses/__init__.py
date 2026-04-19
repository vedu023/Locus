"""Lens-specific backend logic for Locus."""

from app.lenses.investor import (
    InvestorCompanySummary,
    InvestorRunInput,
    InvestorRunSummaryResponse,
    InvestorRunSummaryStats,
    build_investor_company_search_request,
    build_investor_founder_search_request,
    build_investor_signal_summaries,
    score_investor_company,
)
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
    "InvestorCompanySummary",
    "InvestorRunInput",
    "InvestorRunSummaryResponse",
    "InvestorRunSummaryStats",
    "RecruitingCandidateSummary",
    "RecruitingLocationAggregate",
    "RecruitingRunInput",
    "RecruitingRunSummaryResponse",
    "RecruitingRunSummaryStats",
    "SalesCompanySummary",
    "SalesRunInput",
    "SalesRunSummaryResponse",
    "SalesRunSummaryStats",
    "build_investor_company_search_request",
    "build_investor_founder_search_request",
    "build_investor_signal_summaries",
    "build_recruiting_search_request",
    "build_sales_buyer_search_request",
    "score_investor_company",
    "score_recruiting_person",
    "score_sales_company",
]
