from __future__ import annotations

from app.api.deps import get_geocoder
from app.geo.geocode import GeocodeResult, StaticGeocoder
from app.main import app
from app.runs import service as run_service


def test_recruiting_run_builds_filters_and_summary(client, monkeypatch):
    geocoder = StaticGeocoder(
        {
            "bengaluru, karnataka, india": GeocodeResult(
                status="mapped",
                latitude=12.9716,
                longitude=77.5946,
                precision="city",
                confidence=0.92,
                provider="static",
            ),
            "mumbai, maharashtra, india": GeocodeResult(
                status="mapped",
                latitude=19.076,
                longitude=72.8777,
                precision="city",
                confidence=0.9,
                provider="static",
            ),
        }
    )
    app.dependency_overrides[get_geocoder] = lambda: geocoder

    captured_request: dict[str, object] = {}

    def fake_person_search(_client, request):
        captured_request["payload"] = request.model_dump(exclude_none=True)
        return {
            "results": [
                {
                    "crustdata_person_id": "prs-1",
                    "basic_profile": {
                        "name": "Jane Doe",
                        "headline": "VP Engineering | Python platform leader",
                        "location": {
                            "city": "Bengaluru",
                            "state": "Karnataka",
                            "country": "India",
                            "full_location": "Bengaluru, Karnataka, India",
                        },
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "VP Engineering",
                                "company_name": "Acme",
                                "company_website_domain": "acme.com",
                                "seniority_level": "vp",
                                "function_category": "engineering",
                            }
                        }
                    },
                    "contact": {"has_business_email": True, "has_phone_number": True},
                    "social_handles": {
                        "professional_network_identifier": {
                            "profile_url": "https://linkedin.com/in/jane-doe"
                        }
                    },
                },
                {
                    "crustdata_person_id": "prs-2",
                    "basic_profile": {
                        "name": "John Roe",
                        "headline": "Engineering Manager building cloud systems",
                        "location": {
                            "city": "Bengaluru",
                            "state": "Karnataka",
                            "country": "India",
                            "full_location": "Bengaluru, Karnataka, India",
                        },
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "Engineering Manager",
                                "company_name": "Bravo",
                                "company_website_domain": "bravo.com",
                                "seniority_level": "director",
                                "function_category": "engineering",
                            }
                        }
                    },
                    "contact": {"has_phone_number": True},
                    "social_handles": {
                        "professional_network_identifier": {
                            "profile_url": "https://linkedin.com/in/john-roe"
                        }
                    },
                },
                {
                    "crustdata_person_id": "prs-3",
                    "basic_profile": {
                        "name": "Priya Patel",
                        "headline": "Talent partner",
                        "location": {
                            "city": "Mumbai",
                            "state": "Maharashtra",
                            "country": "India",
                            "full_location": "Mumbai, Maharashtra, India",
                        },
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "Recruiter",
                                "company_name": "Acme",
                                "company_website_domain": "acme.com",
                                "seniority_level": "manager",
                                "function_category": "people",
                            }
                        }
                    },
                    "contact": {"has_personal_email": True},
                    "social_handles": {
                        "professional_network_identifier": {
                            "profile_url": "https://linkedin.com/in/priya-patel"
                        }
                    },
                },
            ]
        }

    monkeypatch.setattr(run_service, "person_search", fake_person_search)

    response = client.post(
        "/api/runs",
        json={
            "lens": "recruiting",
            "title": "Recruiting engine run",
            "input": {
                "search": {
                    "fields": ["basic_profile.name"],
                    "limit": 10,
                },
                "target_titles": ["Engineering", "VP"],
                "target_seniorities": ["vp", "director"],
                "target_functions": ["engineering"],
                "target_skills": ["Python"],
                "radius": {
                    "latitude": 12.9716,
                    "longitude": 77.5946,
                    "radius_km": 50,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_counts"]["people"] == 3
    assert payload["result_counts"]["employers"] == 2

    search_payload = captured_request["payload"]
    assert isinstance(search_payload, dict)
    assert "filters" in search_payload
    filters = search_payload["filters"]
    assert isinstance(filters, dict)
    assert filters["op"] == "and"
    conditions = filters["conditions"]
    assert isinstance(conditions, list)
    fields = {condition["field"] for condition in conditions}
    assert "experience.employment_details.current.title" in fields
    assert "experience.employment_details.current.seniority_level" in fields
    assert "experience.employment_details.current.function_category" in fields
    assert "basic_profile.headline" in fields
    assert "basic_profile.location" in fields

    run_id = payload["run_id"]
    summary_response = client.get(f"/api/runs/{run_id}/recruiting-summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["summary"]["people_count"] == 3
    assert summary_payload["summary"]["mapped_people_count"] == 3
    assert summary_payload["summary"]["employer_count"] == 2
    assert summary_payload["candidates"][0]["name"] == "Jane Doe"
    assert (
        summary_payload["candidates"][0]["lens_score"]
        > summary_payload["candidates"][1]["lens_score"]
    )
    assert summary_payload["locations"][0]["raw_label"] == "Bengaluru, Karnataka, India"
    assert summary_payload["locations"][0]["people_count"] == 2
    assert summary_payload["locations"][0]["employer_count"] == 2


def test_recruiting_summary_rejects_non_recruiting_runs(client, monkeypatch):
    monkeypatch.setattr(
        run_service,
        "company_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_company_id": "cmp-11",
                    "basic_info": {"name": "Acme", "primary_domain": "acme.com"},
                    "locations": {"headquarters": "Bengaluru, Karnataka, India"},
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
    summary_response = client.get(f"/api/runs/{run_id}/recruiting-summary")
    assert summary_response.status_code == 400
    assert summary_response.json()["error"]["code"] == "BAD_INPUT"
