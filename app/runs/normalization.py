from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class NormalizedLocation:
    location_key: str
    raw_label: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None


@dataclass
class NormalizedCompany:
    crustdata_company_id: str | None
    name: str
    primary_domain: str | None
    website: str | None
    professional_network_url: str | None
    industry: str | None
    company_type: str | None
    year_founded: int | None
    employee_count: int | None
    employee_count_range: str | None
    funding_total_usd: float | None
    funding_last_round_type: str | None
    funding_last_round_amount_usd: float | None
    funding_last_date: date | None
    location: NormalizedLocation | None
    raw: dict[str, Any]


@dataclass
class NormalizedPerson:
    crustdata_person_id: str | None
    name: str
    professional_network_url: str | None
    headline: str | None
    current_title: str | None
    current_company_name: str | None
    current_company_domain: str | None
    seniority_level: str | None
    function_category: str | None
    has_business_email: bool | None
    has_personal_email: bool | None
    has_phone_number: bool | None
    location: NormalizedLocation | None
    raw: dict[str, Any]


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _clean_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _normalize_location_key(
    *,
    raw_label: str,
    city: str | None,
    region: str | None,
    country: str | None,
) -> str:
    if city:
        return "|".join(
            [
                city.strip().lower(),
                (region or "").strip().lower(),
                (country or "").strip().lower(),
            ]
        )
    return raw_label.strip().lower()


def normalize_location_from_company(payload: dict[str, Any]) -> NormalizedLocation | None:
    locations = payload.get("locations") if isinstance(payload.get("locations"), dict) else {}
    city = _clean_string(locations.get("hq_city"))
    region = _clean_string(locations.get("hq_state"))
    country = _clean_string(locations.get("hq_country"))
    raw_label = _clean_string(locations.get("headquarters"))

    if not raw_label and any([city, region, country]):
        raw_label = ", ".join(part for part in [city, region, country] if part)

    if not raw_label:
        return None

    return NormalizedLocation(
        location_key=_normalize_location_key(
            raw_label=raw_label,
            city=city,
            region=region,
            country=country,
        ),
        raw_label=raw_label,
        city=city,
        region=region,
        country=country,
    )


def normalize_location_from_person(payload: dict[str, Any]) -> NormalizedLocation | None:
    basic_profile = (
        payload.get("basic_profile") if isinstance(payload.get("basic_profile"), dict) else {}
    )
    location = (
        basic_profile.get("location") if isinstance(basic_profile.get("location"), dict) else {}
    )
    professional_network = (
        payload.get("professional_network")
        if isinstance(payload.get("professional_network"), dict)
        else {}
    )
    network_location = (
        professional_network.get("location")
        if isinstance(professional_network.get("location"), dict)
        else {}
    )

    city = _clean_string(location.get("city"))
    region = _clean_string(location.get("state"))
    country = _clean_string(location.get("country"))
    raw_label = _clean_string(location.get("full_location")) or _clean_string(
        network_location.get("raw")
    )

    if not raw_label and any([city, region, country]):
        raw_label = ", ".join(part for part in [city, region, country] if part)

    if not raw_label:
        return None

    return NormalizedLocation(
        location_key=_normalize_location_key(
            raw_label=raw_label,
            city=city,
            region=region,
            country=country,
        ),
        raw_label=raw_label,
        city=city,
        region=region,
        country=country,
    )


def normalize_company(payload: dict[str, Any]) -> NormalizedCompany:
    basic_info = payload.get("basic_info") if isinstance(payload.get("basic_info"), dict) else {}
    taxonomy = payload.get("taxonomy") if isinstance(payload.get("taxonomy"), dict) else {}
    headcount = payload.get("headcount") if isinstance(payload.get("headcount"), dict) else {}
    funding = payload.get("funding") if isinstance(payload.get("funding"), dict) else {}

    return NormalizedCompany(
        crustdata_company_id=_clean_string(
            payload.get("crustdata_company_id") or payload.get("id")
        ),
        name=_clean_string(basic_info.get("name"))
        or _clean_string(payload.get("name"))
        or "Unknown company",
        primary_domain=_clean_string(
            basic_info.get("primary_domain")
            or payload.get("primary_domain")
            or payload.get("domain")
        ),
        website=_clean_string(basic_info.get("website") or payload.get("website")),
        professional_network_url=_clean_string(payload.get("professional_network_url")),
        industry=_clean_string(
            taxonomy.get("professional_network_industry") or payload.get("industry")
        ),
        company_type=_clean_string(basic_info.get("company_type")),
        year_founded=_clean_int(basic_info.get("year_founded")),
        employee_count=_clean_int(headcount.get("total") or payload.get("employee_count")),
        employee_count_range=_clean_string(
            headcount.get("range") or payload.get("employee_count_range")
        ),
        funding_total_usd=_clean_float(funding.get("total_investment_usd")),
        funding_last_round_type=_clean_string(funding.get("last_round_type")),
        funding_last_round_amount_usd=_clean_float(funding.get("last_round_amount_usd")),
        funding_last_date=_clean_date(funding.get("last_fundraise_date")),
        location=normalize_location_from_company(payload),
        raw=payload,
    )


def normalize_person(payload: dict[str, Any]) -> NormalizedPerson:
    basic_profile = (
        payload.get("basic_profile") if isinstance(payload.get("basic_profile"), dict) else {}
    )
    experience = payload.get("experience") if isinstance(payload.get("experience"), dict) else {}
    employment_details = (
        experience.get("employment_details")
        if isinstance(experience.get("employment_details"), dict)
        else {}
    )
    current = (
        employment_details.get("current")
        if isinstance(employment_details.get("current"), dict)
        else {}
    )
    contact = payload.get("contact") if isinstance(payload.get("contact"), dict) else {}
    social_handles = (
        payload.get("social_handles") if isinstance(payload.get("social_handles"), dict) else {}
    )
    professional_network_identifier = (
        social_handles.get("professional_network_identifier")
        if isinstance(social_handles.get("professional_network_identifier"), dict)
        else {}
    )

    return NormalizedPerson(
        crustdata_person_id=_clean_string(payload.get("crustdata_person_id") or payload.get("id")),
        name=_clean_string(basic_profile.get("name"))
        or _clean_string(payload.get("name"))
        or "Unknown person",
        professional_network_url=_clean_string(
            professional_network_identifier.get("profile_url")
            or payload.get("professional_network_url")
        ),
        headline=_clean_string(basic_profile.get("headline") or payload.get("headline")),
        current_title=_clean_string(current.get("title") or payload.get("current_title")),
        current_company_name=_clean_string(
            current.get("company_name") or payload.get("current_company_name")
        ),
        current_company_domain=_clean_string(
            current.get("company_website_domain") or payload.get("current_company_domain")
        ),
        seniority_level=_clean_string(
            current.get("seniority_level") or payload.get("seniority_level")
        ),
        function_category=_clean_string(
            current.get("function_category") or payload.get("function_category")
        ),
        has_business_email=contact.get("has_business_email"),
        has_personal_email=contact.get("has_personal_email"),
        has_phone_number=contact.get("has_phone_number"),
        location=normalize_location_from_person(payload),
        raw=payload,
    )


def extract_results(payload: dict[str, Any], entity_type: str) -> list[dict[str, Any]]:
    candidates = [
        payload.get("results"),
        payload.get("data"),
        payload.get("items"),
        payload.get("companies") if entity_type == "company" else payload.get("people"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

    if isinstance(payload.get("data"), dict):
        nested = payload["data"].get("results")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]

    return []
