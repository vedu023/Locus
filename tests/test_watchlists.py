from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.models import Company, Location, Person, Signal
from app.db.session import get_session_factory
from app.entities import service as entity_service
from app.runs import service as run_service


def _seed_company(*, domain: str = "acme.com", name: str = "Acme", raw: dict | None = None) -> str:
    session = get_session_factory()()
    location = Location(
        location_key=f"{name.lower()}-location",
        raw_label="San Francisco, California, United States",
        city="San Francisco",
        region="California",
        country="United States",
        country_code="US",
        latitude=37.7749,
        longitude=-122.4194,
        geocode_status="mapped",
        geocode_precision="city",
    )
    session.add(location)
    session.flush()
    company = Company(
        name=name,
        primary_domain=domain,
        crustdata_company_id=f"{name.lower()}-company",
        industry="Software",
        raw=raw or {"basic_info": {"name": name, "primary_domain": domain}},
        hq_location_id=location.id,
    )
    session.add(company)
    session.commit()
    company_id = company.id
    session.close()
    return company_id


def _seed_person(*, company_domain: str = "acme.com", company_name: str = "Acme") -> str:
    session = get_session_factory()()
    location = Location(
        location_key=f"{company_name.lower()}-person-location",
        raw_label="Bengaluru, Karnataka, India",
        city="Bengaluru",
        region="Karnataka",
        country="India",
        country_code="IN",
        latitude=12.9716,
        longitude=77.5946,
        geocode_status="mapped",
        geocode_precision="city",
    )
    session.add(location)
    session.flush()
    person = Person(
        name="Jane Doe",
        crustdata_person_id="person-1",
        current_title="Engineer",
        current_company_name=company_name,
        current_company_domain=company_domain,
        professional_network_url="https://linkedin.com/in/jane-doe",
        raw={"basic_profile": {"name": "Jane Doe"}},
        location_id=location.id,
    )
    session.add(person)
    session.commit()
    person_id = person.id
    session.close()
    return person_id


def _add_signal(
    *,
    entity_type: str,
    company_id: str | None = None,
    person_id: str | None = None,
) -> None:
    session = get_session_factory()()
    signal = Signal(
        entity_type=entity_type,
        company_id=company_id,
        person_id=person_id,
        signal_type="funding" if entity_type == "company" else "profile",
        source="test",
        title="Seed signal",
        description="Signal description",
        confidence=0.8,
        occurred_at=datetime.now(timezone.utc),
        raw={"source": "test"},
    )
    session.add(signal)
    session.commit()
    session.close()


def test_watchlist_crud_items_and_signal_timeline(client):
    company_id = _seed_company()
    person_id = _seed_person()
    _add_signal(entity_type="company", company_id=company_id)
    _add_signal(entity_type="person", person_id=person_id)

    create_response = client.post(
        "/api/watchlists",
        json={"name": "Priority", "lens": "sales", "description": "Top targets"},
    )
    assert create_response.status_code == 201
    watchlist_id = create_response.json()["watchlist_id"]

    add_company = client.post(
        f"/api/watchlists/{watchlist_id}/items",
        json={"entity_type": "company", "company_id": company_id},
    )
    assert add_company.status_code == 201

    add_person = client.post(
        f"/api/watchlists/{watchlist_id}/items",
        json={"entity_type": "person", "person_id": person_id, "notes": "Warm intro"},
    )
    assert add_person.status_code == 201
    assert add_person.json()["item_count"] == 2

    list_response = client.get("/api/watchlists")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["item_count"] == 2

    signals_response = client.get(f"/api/watchlists/{watchlist_id}/signals")
    assert signals_response.status_code == 200
    signals_payload = signals_response.json()
    assert len(signals_payload["signals"]) == 2
    assert {item["entity_type"] for item in signals_payload["signals"]} == {"company", "person"}

    item_id = add_person.json()["items"][1]["item_id"]
    remove_response = client.delete(f"/api/watchlists/{watchlist_id}/items/{item_id}")
    assert remove_response.status_code == 200
    assert remove_response.json()["item_count"] == 1

    delete_response = client.delete(f"/api/watchlists/{watchlist_id}")
    assert delete_response.status_code == 204


def test_enrich_routes_and_watchlist_refresh(client, monkeypatch):
    company_id = _seed_company(raw={"basic_info": {"name": "Acme", "primary_domain": "acme.com"}})
    person_id = _seed_person()

    monkeypatch.setattr(
        entity_service,
        "company_enrich",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_company_id": "acme-company",
                    "basic_info": {
                        "name": "Acme",
                        "primary_domain": "acme.com",
                        "website": "https://acme.com",
                        "company_type": "private",
                    },
                    "taxonomy": {
                        "professional_network_industry": "Software",
                        "categories": ["Developer Tools"],
                    },
                    "headcount": {"total": 140},
                    "funding": {
                        "total_investment_usd": 15000000,
                        "last_round_type": "series_a",
                        "last_round_amount_usd": 10000000,
                        "last_fundraise_date": "2025-08-01",
                    },
                    "followers": {"six_months_growth_percent": 42},
                    "hiring": {"openings_count": 10, "openings_growth_percent": 75},
                    "roles": {"growth_6m": 25},
                    "locations": {
                        "headquarters": "San Francisco, California, United States",
                        "hq_city": "San Francisco",
                        "hq_state": "California",
                        "hq_country": "United States",
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(
        entity_service,
        "person_enrich",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_person_id": "person-1",
                    "basic_profile": {
                        "name": "Jane Doe",
                        "headline": "Platform engineer",
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
                                "title": "Senior Engineer",
                                "company_name": "Acme",
                                "company_website_domain": "acme.com",
                                "seniority_level": "senior",
                                "function_category": "engineering",
                            }
                        }
                    },
                    "contact": {"has_business_email": True},
                    "social_handles": {
                        "professional_network_identifier": {
                            "profile_url": "https://linkedin.com/in/jane-doe"
                        }
                    },
                }
            ]
        },
    )

    company_enrich_response = client.post(f"/api/entities/company/{company_id}/enrich")
    assert company_enrich_response.status_code == 200
    assert company_enrich_response.json()["signal_count"] == 3

    person_enrich_response = client.post(f"/api/entities/person/{person_id}/enrich")
    assert person_enrich_response.status_code == 200
    assert person_enrich_response.json()["entity_type"] == "person"

    create_watchlist = client.post("/api/watchlists", json={"name": "Refresh me"})
    watchlist_id = create_watchlist.json()["watchlist_id"]
    client.post(
        f"/api/watchlists/{watchlist_id}/items",
        json={"entity_type": "company", "company_id": company_id},
    )
    client.post(
        f"/api/watchlists/{watchlist_id}/items",
        json={"entity_type": "person", "person_id": person_id},
    )

    refresh_response = client.post(f"/api/watchlists/{watchlist_id}/refresh")
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["refreshed_companies"] == 1
    assert refresh_payload["refreshed_people"] == 1
    assert refresh_payload["signals_upserted"] == 3


def test_quota_and_admin_views(client, monkeypatch):
    monkeypatch.setenv("LOCUS_DAILY_ENRICH_LIMIT_PER_USER", "1")
    get_settings.cache_clear()

    company_id = _seed_company(raw={"basic_info": {"name": "Acme", "primary_domain": "acme.com"}})
    monkeypatch.setattr(
        entity_service,
        "company_enrich",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_company_id": "acme-company",
                    "basic_info": {"name": "Acme", "primary_domain": "acme.com"},
                    "locations": {"headquarters": "San Francisco, California, United States"},
                }
            ]
        },
    )

    first = client.post(f"/api/entities/company/{company_id}/enrich")
    assert first.status_code == 200

    second = client.post(f"/api/entities/company/{company_id}/enrich")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "QUOTA_EXCEEDED"

    raw_forbidden = client.get(
        f"/api/entities/company/{company_id}/raw",
        headers={"X-Dev-User-Is-Admin": "false"},
    )
    assert raw_forbidden.status_code == 403

    raw_allowed = client.get(f"/api/entities/company/{company_id}/raw")
    assert raw_allowed.status_code == 200
    assert raw_allowed.json()["entity_type"] == "company"

    metrics = client.get("/api/admin/metrics")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert metrics_payload["usage_today"]["entity_enrich"] == 1
    assert metrics_payload["signals"] >= 0


def test_kill_switch_blocks_run_creation(client, monkeypatch):
    monkeypatch.setenv("LOCUS_GLOBAL_KILL_SWITCH", "true")
    get_settings.cache_clear()

    monkeypatch.setattr(
        run_service,
        "company_search",
        lambda _client, _request: {"results": []},
    )

    response = client.post(
        "/api/runs",
        json={
            "lens": "investor",
            "input": {"search": {"fields": ["basic_info.name"], "limit": 1}},
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_PAUSED"
