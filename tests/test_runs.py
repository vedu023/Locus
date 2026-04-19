from __future__ import annotations

from app.runs import service as run_service


def test_create_sales_run_persists_companies_and_locations(client, monkeypatch):
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
                        "website": "https://acme.com",
                        "company_type": "private",
                        "year_founded": 2020,
                    },
                    "taxonomy": {"professional_network_industry": "Software"},
                    "headcount": {"total": 42},
                    "locations": {
                        "headquarters": "Bengaluru, Karnataka, India",
                        "hq_city": "Bengaluru",
                        "hq_state": "Karnataka",
                        "hq_country": "India",
                    },
                }
            ]
        },
    )

    response = client.post(
        "/api/runs",
        json={
            "lens": "sales",
            "title": "Sales run",
            "input": {
                "search": {
                    "fields": ["basic_info.name", "basic_info.primary_domain"],
                    "limit": 10,
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["lens"] == "sales"
    assert payload["result_counts"]["companies"] == 1
    assert payload["result_counts"]["locations"] == 1

    run_id = payload["run_id"]
    get_response = client.get(f"/api/runs/{run_id}")
    get_payload = get_response.json()
    assert get_response.status_code == 200
    assert get_payload["title"] == "Sales run"
    assert get_payload["normalized_filters"] == {}
    assert get_payload["result_counts"]["companies"] == 1


def test_create_recruiting_run_persists_people(client, monkeypatch):
    monkeypatch.setattr(
        run_service,
        "person_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_person_id": "prs-1",
                    "basic_profile": {
                        "name": "Jane Doe",
                        "headline": "VP Engineering",
                        "location": {
                            "city": "Bengaluru",
                            "state": "Karnataka",
                            "country": "India",
                        },
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "VP Engineering",
                                "company_name": "Acme",
                                "company_website_domain": "acme.com",
                                "seniority_level": "VP",
                                "function_category": "engineering",
                            }
                        }
                    },
                    "contact": {"has_business_email": True},
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
                    "fields": ["basic_profile.name", "basic_profile.location"],
                    "limit": 10,
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_counts"]["people"] == 1
    assert payload["result_counts"]["primary_entity_type"] == "person"


def test_get_run_returns_404_for_unknown_id(client):
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
