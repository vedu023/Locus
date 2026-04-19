from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.crustdata.filters import FilterCondition, FilterGroup, to_safe_contains_pattern
from app.crustdata.types import PersonSearchRequest
from app.db.models import Location, Person
from app.lenses.scoring import weighted_average

DEFAULT_CANDIDATE_FIELDS = [
    "basic_profile.name",
    "basic_profile.headline",
    "basic_profile.location",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "experience.employment_details.current.seniority_level",
    "experience.employment_details.current.function_category",
    "contact.has_business_email",
    "contact.has_personal_email",
    "contact.has_phone_number",
    "social_handles.professional_network_identifier.profile_url",
]


class RadiusFilter(BaseModel):
    field: str = "basic_profile.location"
    latitude: float
    longitude: float
    radius_km: float = Field(ge=1, le=1000)


class RecruitingScoreWeights(BaseModel):
    title_fit: float = Field(default=0.24, ge=0)
    seniority_fit: float = Field(default=0.18, ge=0)
    function_fit: float = Field(default=0.14, ge=0)
    skill_fit: float = Field(default=0.18, ge=0)
    contact_fit: float = Field(default=0.14, ge=0)
    employer_signal: float = Field(default=0.12, ge=0)


class RecruitingRunInput(BaseModel):
    search: PersonSearchRequest
    target_titles: list[str] = Field(default_factory=list)
    target_seniorities: list[str] = Field(default_factory=list)
    target_functions: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    radius: RadiusFilter | None = None
    candidate_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_CANDIDATE_FIELDS))
    top_candidate_limit: int = Field(default=25, ge=1, le=100)
    score_weights: RecruitingScoreWeights = Field(default_factory=RecruitingScoreWeights)


class RecruitingCandidateSummary(BaseModel):
    person_id: str
    name: str
    title: str | None
    seniority: str | None
    function_category: str | None
    current_company_name: str | None
    current_company_domain: str | None
    headline: str | None
    has_business_email: bool | None
    has_phone_number: bool | None
    lens_score: float
    location: dict[str, Any]
    score_breakdown: dict[str, Any]


class RecruitingLocationAggregate(BaseModel):
    location_id: str | None
    raw_label: str | None
    latitude: float | None
    longitude: float | None
    status: str
    precision: str | None
    people_count: int
    employer_count: int
    employers: list[str]


class RecruitingRunSummaryStats(BaseModel):
    people_count: int
    mapped_people_count: int
    employer_count: int
    average_candidate_score: float
    top_candidate_score: float | None


class RecruitingRunSummaryResponse(BaseModel):
    run_id: str
    title: str | None
    summary: RecruitingRunSummaryStats
    candidates: list[RecruitingCandidateSummary]
    locations: list[RecruitingLocationAggregate]


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _contains_any(value: str | None, targets: list[str]) -> bool:
    haystack = _normalize_text(value)
    normalized_targets = [_normalize_text(target) for target in targets if _normalize_text(target)]
    if not normalized_targets:
        return False
    return any(target in haystack for target in normalized_targets)


def _exact_match(value: str | None, targets: list[str]) -> bool:
    normalized_value = _normalize_text(value)
    normalized_targets = {_normalize_text(target) for target in targets if _normalize_text(target)}
    if not normalized_targets:
        return False
    return normalized_value in normalized_targets


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


def build_recruiting_search_request(recruiting_input: RecruitingRunInput) -> PersonSearchRequest:
    conditions: list[FilterCondition] = []
    if recruiting_input.target_titles:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.title",
                type="(.)",
                value=to_safe_contains_pattern(recruiting_input.target_titles),
            )
        )
    if recruiting_input.target_seniorities:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.seniority_level",
                type="in",
                value=recruiting_input.target_seniorities,
            )
        )
    if recruiting_input.target_functions:
        conditions.append(
            FilterCondition(
                field="experience.employment_details.current.function_category",
                type="in",
                value=recruiting_input.target_functions,
            )
        )
    if recruiting_input.target_skills:
        conditions.append(
            FilterCondition(
                field="basic_profile.headline",
                type="(.)",
                value=to_safe_contains_pattern(recruiting_input.target_skills),
            )
        )
    if recruiting_input.radius is not None:
        conditions.append(
            FilterCondition(
                field=recruiting_input.radius.field,
                type="geo_distance",
                value={
                    "latitude": recruiting_input.radius.latitude,
                    "longitude": recruiting_input.radius.longitude,
                    "radius_km": recruiting_input.radius.radius_km,
                },
            )
        )

    search = recruiting_input.search
    return PersonSearchRequest(
        fields=recruiting_input.candidate_fields or search.fields,
        filters=_merge_filters(search.filters, conditions),
        limit=search.limit,
        cursor=search.cursor,
    )


def score_recruiting_person(
    *,
    person: Person,
    recruiting_input: RecruitingRunInput,
    location: Location | None = None,
) -> tuple[float, dict[str, Any]]:
    title_score = 0.6
    if recruiting_input.target_titles:
        title_score = (
            1.0
            if _contains_any(person.current_title, recruiting_input.target_titles)
            else 0.1
        )

    seniority_score = 0.6
    if recruiting_input.target_seniorities:
        seniority_score = (
            1.0
            if _exact_match(person.seniority_level, recruiting_input.target_seniorities)
            else 0.1
        )

    function_score = 0.6
    if recruiting_input.target_functions:
        function_score = (
            1.0
            if _exact_match(person.function_category, recruiting_input.target_functions)
            else 0.1
        )

    skill_score = 0.6
    if recruiting_input.target_skills:
        headline = " ".join(part for part in [person.headline, person.current_title] if part)
        skill_score = 1.0 if _contains_any(headline, recruiting_input.target_skills) else 0.1

    contact_score = 0.2
    if person.has_business_email or person.has_phone_number:
        contact_score = 1.0
    elif person.has_personal_email:
        contact_score = 0.65

    employer_signal = 0.25
    if person.current_company_name and person.current_company_domain:
        employer_signal = 1.0
    elif person.current_company_name or person.current_company_domain:
        employer_signal = 0.65

    weights = recruiting_input.score_weights
    weighted_inputs = {
        "title_fit": (title_score, weights.title_fit),
        "seniority_fit": (seniority_score, weights.seniority_fit),
        "function_fit": (function_score, weights.function_fit),
        "skill_fit": (skill_score, weights.skill_fit),
        "contact_fit": (contact_score, weights.contact_fit),
        "employer_signal": (employer_signal, weights.employer_signal),
    }
    score = round(weighted_average(weighted_inputs) * 100, 2)

    return score, {
        "title_fit": round(title_score, 3),
        "seniority_fit": round(seniority_score, 3),
        "function_fit": round(function_score, 3),
        "skill_fit": round(skill_score, 3),
        "contact_fit": round(contact_score, 3),
        "employer_signal": round(employer_signal, 3),
        "target_titles": recruiting_input.target_titles,
        "target_seniorities": recruiting_input.target_seniorities,
        "target_functions": recruiting_input.target_functions,
        "target_skills": recruiting_input.target_skills,
        "radius_km": recruiting_input.radius.radius_km if recruiting_input.radius else None,
        "location_status": location.geocode_status if location else "missing",
        "location_precision": location.geocode_precision if location else None,
    }
