from __future__ import annotations

from app.api.deps import get_geocoder
from app.geo.geocode import GeocodeResult, StaticGeocoder
from app.main import app
from app.runs import service as run_service


def test_sales_run_attaches_buyers_and_summary_cards(client, monkeypatch):
    geocoder = StaticGeocoder(
        {
            "san francisco, california, united states": GeocodeResult(
                status="mapped",
                latitude=37.7749,
                longitude=-122.4194,
                precision="city",
                confidence=0.95,
                provider="static",
            )
        }
    )
    app.dependency_overrides[get_geocoder] = lambda: geocoder

    monkeypatch.setattr(
        run_service,
        "company_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_company_id": "cmp-1",
                    "basic_info": {
                        "name": "Acme",
                        "primary_domain": "acme.com",
                        "company_type": "private",
                        "year_founded": 2018,
                    },
                    "taxonomy": {"professional_network_industry": "Software"},
                    "headcount": {"total": 180},
                    "funding": {
                        "total_investment_usd": 25000000,
                        "last_round_type": "series_a",
                        "last_round_amount_usd": 12000000,
                        "last_fundraise_date": "2025-05-01",
                    },
                    "locations": {
                        "headquarters": "San Francisco, California, United States",
                        "hq_city": "San Francisco",
                        "hq_state": "California",
                        "hq_country": "United States",
                    },
                },
                {
                    "crustdata_company_id": "cmp-2",
                    "basic_info": {
                        "name": "Bravo",
                        "primary_domain": "bravo.com",
                        "company_type": "private",
                        "year_founded": 2012,
                    },
                    "taxonomy": {"professional_network_industry": "Manufacturing"},
                    "headcount": {"total": 4500},
                    "funding": {
                        "total_investment_usd": 0,
                    },
                    "locations": {
                        "headquarters": "San Francisco, California, United States",
                        "hq_city": "San Francisco",
                        "hq_state": "California",
                        "hq_country": "United States",
                    },
                },
            ]
        },
    )

    def fake_person_search(_client, request):
        filters = request.model_dump(exclude_none=True)["filters"]
        domain = filters["conditions"][0]["value"]
        if domain == "acme.com":
            return {
                "results": [
                    {
                        "crustdata_person_id": "prs-1",
                        "basic_profile": {
                            "name": "Alice Seller",
                            "headline": "VP Sales at Acme",
                            "location": {
                                "city": "San Francisco",
                                "state": "California",
                                "country": "United States",
                                "full_location": "San Francisco, California, United States",
                            },
                        },
                        "experience": {
                            "employment_details": {
                                "current": {
                                    "title": "VP Sales",
                                    "company_name": "Acme",
                                    "company_website_domain": "acme.com",
                                    "seniority_level": "vp",
                                    "function_category": "sales",
                                }
                            }
                        },
                        "contact": {"has_business_email": True},
                        "social_handles": {
                            "professional_network_identifier": {
                                "profile_url": "https://linkedin.com/in/alice-seller"
                            }
                        },
                    },
                    {
                        "crustdata_person_id": "prs-2",
                        "basic_profile": {
                            "name": "Bob Founder",
                            "headline": "Founder at Acme",
                            "location": {
                                "city": "San Francisco",
                                "state": "California",
                                "country": "United States",
                                "full_location": "San Francisco, California, United States",
                            },
                        },
                        "experience": {
                            "employment_details": {
                                "current": {
                                    "title": "Founder",
                                    "company_name": "Acme",
                                    "company_website_domain": "acme.com",
                                    "seniority_level": "cxo",
                                    "function_category": "executive",
                                }
                            }
                        },
                        "contact": {"has_business_email": True},
                        "social_handles": {
                            "professional_network_identifier": {
                                "profile_url": "https://linkedin.com/in/bob-founder"
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
            "lens": "sales",
            "title": "Sales engine run",
            "input": {
                "search": {
                    "fields": ["basic_info.name", "basic_info.primary_domain"],
                    "limit": 10,
                },
                "preferred_industries": ["Software"],
                "top_company_limit": 1,
                "buyers_per_company": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_counts"]["companies"] == 2
    assert payload["result_counts"]["buyers"] == 2
    assert payload["result_counts"]["buyer_companies"] == 1

    run_id = payload["run_id"]
    summary_response = client.get(f"/api/runs/{run_id}/sales-summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["summary"]["company_count"] == 2
    assert summary_payload["summary"]["buyer_count"] == 2
    assert summary_payload["companies"][0]["name"] == "Acme"
    assert summary_payload["companies"][0]["buyer_count"] == 2
    assert summary_payload["companies"][0]["buyers"][0]["name"] == "Alice Seller"
    assert (
        summary_payload["companies"][0]["lens_score"]
        > summary_payload["companies"][1]["lens_score"]
    )
    assert summary_payload["companies"][0]["score_breakdown"]["buyer_count"] == 2


def test_sales_summary_rejects_non_sales_runs(client, monkeypatch):
    monkeypatch.setattr(
        run_service,
        "person_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_person_id": "prs-9",
                    "basic_profile": {"name": "Jane Doe"},
                }
            ]
        },
    )

    response = client.post(
        "/api/runs",
        json={
            "lens": "recruiting",
            "input": {
                "search": {
                    "fields": ["basic_profile.name"],
                    "limit": 10,
                }
            },
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    summary_response = client.get(f"/api/runs/{run_id}/sales-summary")
    assert summary_response.status_code == 400
    assert summary_response.json()["error"]["code"] == "BAD_INPUT"
