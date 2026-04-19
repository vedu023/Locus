from __future__ import annotations

from app.api.deps import get_geocoder
from app.crustdata.cache import CacheBackend, InMemoryCache
from app.geo.geocode import CachedGeocoder, GeocodeQuery, GeocodeResult, StaticGeocoder
from app.main import app
from app.runs import service as run_service


def test_cached_geocoder_uses_cache():
    static_geocoder = StaticGeocoder(
        {
            "bengaluru, karnataka, india": GeocodeResult(
                status="mapped",
                latitude=12.9716,
                longitude=77.5946,
                precision="city",
                confidence=0.9,
                provider="static",
            )
        }
    )
    geocoder = CachedGeocoder(
        static_geocoder,
        cache_backend=CacheBackend(redis_client=None, fallback=InMemoryCache()),
        ttl_seconds=60,
    )
    query = GeocodeQuery(raw_label="Bengaluru, Karnataka, India")

    first = geocoder.geocode(query)
    second = geocoder.geocode(query)

    assert first == second
    assert static_geocoder.calls == ["bengaluru, karnataka, india"]


def test_run_clusters_group_entities_by_location(client, monkeypatch):
    geocoder = StaticGeocoder(
        {
            "bengaluru, karnataka, india": GeocodeResult(
                status="mapped",
                latitude=12.9716,
                longitude=77.5946,
                precision="city",
                confidence=0.92,
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
                    },
                    "locations": {
                        "headquarters": "Bengaluru, Karnataka, India",
                        "hq_city": "Bengaluru",
                        "hq_state": "Karnataka",
                        "hq_country": "India",
                    },
                },
                {
                    "crustdata_company_id": "cmp-2",
                    "basic_info": {
                        "name": "Bravo",
                        "primary_domain": "bravo.com",
                    },
                    "locations": {
                        "headquarters": "Bengaluru, Karnataka, India",
                        "hq_city": "Bengaluru",
                        "hq_state": "Karnataka",
                        "hq_country": "India",
                    },
                },
            ]
        },
    )

    create_response = client.post(
        "/api/runs",
        json={
            "lens": "sales",
            "title": "Map cluster run",
            "input": {
                "search": {
                    "fields": ["basic_info.name", "basic_info.primary_domain"],
                    "limit": 10,
                }
            },
        },
    )
    assert create_response.status_code == 200

    run_id = create_response.json()["run_id"]
    run_response = client.get(f"/api/runs/{run_id}")
    run_payload = run_response.json()
    assert run_payload["result_counts"]["mapped"] == 2
    assert run_payload["result_counts"]["unmapped"] == 0
    assert run_payload["result_counts"]["low_precision"] == 0

    clusters_response = client.get(
        f"/api/runs/{run_id}/clusters",
        params={
            "zoom": 7,
            "min_lat": 10,
            "min_lng": 70,
            "max_lat": 15,
            "max_lng": 80,
        },
    )
    assert clusters_response.status_code == 200
    clusters_payload = clusters_response.json()
    assert clusters_payload["summary"]["mapped_count"] == 2
    assert len(clusters_payload["clusters"]) == 1
    cluster = clusters_payload["clusters"][0]
    assert cluster["entity_count"] == 2
    assert cluster["company_count"] == 2
    assert cluster["location_count"] == 1

    entities_response = client.get(
        f"/api/runs/{run_id}/entities",
        params={"location_id": cluster["location_ids"][0]},
    )
    assert entities_response.status_code == 200
    entity_names = [item["name"] for item in entities_response.json()["items"]]
    assert entity_names == ["Acme", "Bravo"]


def test_run_entities_include_unmapped_and_low_precision(client, monkeypatch):
    geocoder = StaticGeocoder(
        {
            "india": GeocodeResult(
                status="mapped",
                latitude=20.5937,
                longitude=78.9629,
                precision="country",
                confidence=0.45,
                provider="static",
            )
        }
    )
    app.dependency_overrides[get_geocoder] = lambda: geocoder

    monkeypatch.setattr(
        run_service,
        "person_search",
        lambda _client, _request: {
            "results": [
                {
                    "crustdata_person_id": "prs-1",
                    "basic_profile": {
                        "name": "Jane Doe",
                        "location": {
                            "country": "India",
                            "full_location": "India",
                        },
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "VP Engineering",
                                "company_name": "Acme",
                            }
                        }
                    },
                },
                {
                    "crustdata_person_id": "prs-2",
                    "basic_profile": {
                        "name": "John Roe",
                    },
                    "experience": {
                        "employment_details": {
                            "current": {
                                "title": "Engineering Manager",
                                "company_name": "Bravo",
                            }
                        }
                    },
                },
            ]
        },
    )

    create_response = client.post(
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
    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    run_response = client.get(f"/api/runs/{run_id}")
    run_payload = run_response.json()
    assert run_payload["result_counts"]["mapped"] == 1
    assert run_payload["result_counts"]["unmapped"] == 1
    assert run_payload["result_counts"]["low_precision"] == 1

    entities_response = client.get(
        f"/api/runs/{run_id}/entities",
        params={"include_unmapped": "true"},
    )
    assert entities_response.status_code == 200
    entities_payload = entities_response.json()
    assert entities_payload["summary"]["unmapped_count"] == 1
    assert entities_payload["summary"]["low_precision_count"] == 1
    assert len(entities_payload["items"]) == 2
    assert entities_payload["items"][0]["location"]["precision"] == "country"
    assert entities_payload["items"][1]["location"]["status"] == "missing"


def test_clusters_reject_partial_bbox(client):
    response = client.get("/api/runs/does-not-exist/clusters", params={"min_lat": 10})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BBOX"
