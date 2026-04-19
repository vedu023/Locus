from __future__ import annotations

from app.core.errors import AppError

SALES_COMPANY_FIELDS = [
    "crustdata_company_id",
    "basic_info.name",
    "basic_info.primary_domain",
    "basic_info.website",
    "basic_info.company_type",
    "basic_info.year_founded",
    "headcount.total",
    "locations.headquarters",
    "locations.hq_city",
    "locations.hq_state",
    "locations.hq_country",
    "taxonomy.professional_network_industry",
    "funding.total_investment_usd",
    "hiring.openings_count",
    "hiring.openings_growth_percent",
]

SALES_PERSON_FIELDS = [
    "basic_profile.name",
    "basic_profile.headline",
    "basic_profile.location",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "experience.employment_details.current.seniority_level",
    "experience.employment_details.current.function_category",
    "contact.has_business_email",
    "social_handles.professional_network_identifier.profile_url",
    "professional_network.connections",
]

RECRUITING_PERSON_FIELDS = [
    "basic_profile.name",
    "basic_profile.headline",
    "basic_profile.location",
    "basic_profile.location.city",
    "basic_profile.location.state",
    "basic_profile.location.country",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "experience.employment_details.current.seniority_level",
    "experience.employment_details.current.function_category",
    "experience.employment_details.current.years_at_company_raw",
    "skills.professional_network_skills",
    "contact.has_business_email",
    "social_handles.professional_network_identifier.profile_url",
    "professional_network.connections",
    "metadata.updated_at",
]

INVESTOR_COMPANY_FIELDS = [
    "crustdata_company_id",
    "basic_info.name",
    "basic_info.primary_domain",
    "basic_info.website",
    "basic_info.year_founded",
    "basic_info.company_type",
    "basic_info.markets",
    "headcount.total",
    "roles.growth_6m",
    "roles.growth_yoy",
    "locations.headquarters",
    "locations.hq_city",
    "locations.hq_state",
    "locations.hq_country",
    "taxonomy.professional_network_industry",
    "taxonomy.categories",
    "funding.total_investment_usd",
    "funding.last_round_amount_usd",
    "funding.last_fundraise_date",
    "funding.last_round_type",
    "funding.investors",
    "followers.count",
    "followers.six_months_growth_percent",
    "hiring.openings_count",
    "hiring.openings_growth_percent",
]

INVESTOR_FOUNDER_FIELDS = [
    "basic_profile.name",
    "basic_profile.headline",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "social_handles.professional_network_identifier.profile_url",
    "professional_network.connections",
]

LENS_FIELD_PRESETS = {
    "sales": {
        "company": SALES_COMPANY_FIELDS,
        "person": SALES_PERSON_FIELDS,
    },
    "recruiting": {
        "person": RECRUITING_PERSON_FIELDS,
    },
    "investor": {
        "company": INVESTOR_COMPANY_FIELDS,
        "person": INVESTOR_FOUNDER_FIELDS,
    },
}


def get_lens_fields(lens: str, entity_type: str) -> list[str]:
    try:
        return LENS_FIELD_PRESETS[lens][entity_type]
    except KeyError as exc:
        raise AppError(
            code="BAD_INPUT",
            message="Unknown lens or entity type for field preset lookup.",
            status_code=400,
            details={"lens": lens, "entity_type": entity_type},
        ) from exc
