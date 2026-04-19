from __future__ import annotations

from app.api.deps import get_geocoder
from app.geo.geocode import GeocodeResult, StaticGeocoder
from app.main import app
from app.runs import service as run_service


def test_investor_run_builds_filters_and_summary(client, monkeypatch):
    geocoder = StaticGeocoder(
        {
            "san francisco, california, united states": GeocodeResult(
                status="mapped",
                latitude=37.7749,
                longitude=-122.4194,
                precision="city",
                confidence=0.95,
                provider="static",
            ),
            "new york, new york, united states": GeocodeResult(
                status="mapped",
                latitude=40.7128,
                longitude=-74.006,
                precision="city",
                confidence=0.94,
                provider="static",
            ),
        }
    )
    app.dependency_overrides[get_geocoder] = lambda: geocoder

    captured_company_request: dict[str, object] = {}
    founder_search_domains: list[str] = []

    def fake_company_search(_client, request):
        captured_company_request["payload"] = request.model_dump(exclude_none=True)
        return {
            "results": [
                {
                    "crustdata_company_id": "cmp-1",
                    "basic_info": {
                        "name": "Bravo Robotics",
                        "primary_domain": "bravo.com",
                        "website": "https://bravo.com",
                        "company_type": "private",
                        "year_founded": 2017,
                        "markets": ["Industrial Automation"],
                    },
                    "taxonomy": {
                        "professional_network_industry": "Manufacturing",
                        "categories": ["Robotics"],
                    },
                    "headcount": {"total": 60},
                    "funding": {
                        "total_investment_usd": 500000,
                        "last_round_type": "pre_seed",
                        "last_round_amount_usd": 500000,
                        "last_fundraise_date": "2021-02-01",
                    },
                    "followers": {"six_months_growth_percent": 4},
                    "hiring": {"openings_count": 1, "openings_growth_percent": -5},
                    "roles": {"growth_6m": 3},
                    "locations": {
                        "headquarters": "New York, New York, United States",
                        "hq_city": "New York",
                        "hq_state": "New York",
                        "hq_country": "United States",
                    },
                },
                {
                    "crustdata_company_id": "cmp-2",
                    "basic_info": {
                        "name": "Acme AI",
                        "primary_domain": "acme.com",
                        "website": "https://acme.com",
                        "company_type": "private",
                        "year_founded": 2021,
                        "markets": ["AI Infrastructure", "Developer Tools"],
                    },
                    "taxonomy": {
                        "professional_network_industry": "Software",
                        "categories": ["Developer Tools", "Artificial Intelligence"],
                    },
                    "headcount": {"total": 120},
                    "funding": {
                        "total_investment_usd": 32000000,
                        "last_round_type": "series_a",
                        "last_round_amount_usd": 15000000,
                        "last_fundraise_date": "2025-08-01",
                    },
                    "followers": {"six_months_growth_percent": 62},
                    "hiring": {"openings_count": 24, "openings_growth_percent": 135},
                    "roles": {"growth_6m": 48},
                    "locations": {
                        "headquarters": "San Francisco, California, United States",
                        "hq_city": "San Francisco",
                        "hq_state": "California",
                        "hq_country": "United States",
                    },
                },
            ]
        }

    monkeypatch.setattr(run_service, "company_search", fake_company_search)

    def fake_person_search(_client, request):
        payload = request.model_dump(exclude_none=True)
        filters = payload["filters"]
        domain = filters["conditions"][0]["value"]
        founder_search_domains.append(domain)
        if domain == "acme.com":
            return {
                "results": [
                    {
                        "crustdata_person_id": "prs-1",
                        "basic_profile": {
                            "name": "Jane Founder",
                            "headline": "Founder building AI developer tooling",
                        },
                        "experience": {
                            "employment_details": {
                                "current": {
                                    "title": "Founder",
                                    "company_name": "Acme AI",
                                    "company_website_domain": "acme.com",
                                    "seniority_level": "cxo",
                                }
                            }
                        },
                        "social_handles": {
                            "professional_network_identifier": {
                                "profile_url": "https://linkedin.com/in/jane-founder"
                            }
                        },
                    },
                    {
                        "crustdata_person_id": "prs-2",
                        "basic_profile": {
                            "name": "Sam CEO",
                            "headline": "CEO scaling AI infrastructure",
                        },
                        "experience": {
                            "employment_details": {
                                "current": {
                                    "title": "CEO",
                                    "company_name": "Acme AI",
                                    "company_website_domain": "acme.com",
                                    "seniority_level": "cxo",
                                }
                            }
                        },
                        "social_handles": {
                            "professional_network_identifier": {
                                "profile_url": "https://linkedin.com/in/sam-ceo"
                            }
                        },
                    },
                ]
            }
        return {"results": []}

    monkeypatch.setattr(run_service, "person_search", fake_person_search)

    response = client.post(
        "/api/runs",
        json={
            "lens": "investor",
            "title": "Investor engine run",
            "input": {
                "search": {
                    "fields": ["basic_info.name"],
                    "limit": 10,
                },
                "target_markets": ["AI Infrastructure"],
                "target_categories": ["Developer Tools"],
                "min_openings_growth_percent": 20,
                "top_company_limit": 1,
                "founders_per_company": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_counts"]["companies"] == 2
    assert payload["result_counts"]["founders"] == 2
    assert payload["result_counts"]["founder_companies"] == 1
    assert payload["result_counts"]["signals"] == 6
    assert founder_search_domains == ["acme.com"]

    search_payload = captured_company_request["payload"]
    assert isinstance(search_payload, dict)
    assert "filters" in search_payload
    filters = search_payload["filters"]
    assert isinstance(filters, dict)
    assert filters["op"] == "and"
    conditions = filters["conditions"]
    assert isinstance(conditions, list)
    fields = {condition["field"] for condition in conditions}
    assert "basic_info.markets" in fields
    assert "taxonomy.categories" in fields
    assert "hiring.openings_growth_percent" in fields

    run_id = payload["run_id"]
    summary_response = client.get(f"/api/runs/{run_id}/investor-summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["summary"]["company_count"] == 2
    assert summary_payload["summary"]["mapped_company_count"] == 2
    assert summary_payload["summary"]["founder_count"] == 2
    assert summary_payload["summary"]["signal_count"] == 6
    assert summary_payload["companies"][0]["name"] == "Acme AI"
    assert summary_payload["companies"][0]["founder_count"] == 2
    assert summary_payload["companies"][0]["founders"][0]["name"] == "Jane Founder"
    assert (
        summary_payload["companies"][0]["lens_score"]
        > summary_payload["companies"][1]["lens_score"]
    )
    signal_types = {signal["signal_type"] for signal in summary_payload["companies"][0]["signals"]}
    assert signal_types == {"funding", "hiring", "headcount"}


def test_investor_summary_rejects_non_investor_runs(client, monkeypatch):
    monkeypatch.setattr(
        run_service,
        "company_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_company_id": "cmp-11",
                    "basic_info": {"name": "Acme", "primary_domain": "acme.com"},
                    "locations": {"headquarters": "San Francisco, California, United States"},
                }
            ]
        },
    )
    monkeypatch.setattr(
        run_service,
        "person_search",
        lambda _client, _request: {"results": []},
    )

    response = client.post(
        "/api/runs",
        json={
            "lens": "sales",
            "input": {
                "search": {
                    "fields": ["basic_info.name", "basic_info.primary_domain"],
                    "limit": 10,
                }
            },
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    summary_response = client.get(f"/api/runs/{run_id}/investor-summary")
    assert summary_response.status_code == 400
    assert summary_response.json()["error"]["code"] == "BAD_INPUT"
