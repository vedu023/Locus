import httpx
import pytest

from app.core.errors import AppError
from app.crustdata.cache import CacheBackend, InMemoryCache
from app.crustdata.client import CrustdataClient, RateLimiter


def build_test_client(handler, monkeypatch, rpm_limit: int = 12):
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-key")
    monkeypatch.setenv("CRUSTDATA_RPM_LIMIT", str(rpm_limit))

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="https://api.crustdata.com", transport=transport)

    return CrustdataClient(
        http_client=http_client,
        cache_backend=CacheBackend(redis_client=None, fallback=InMemoryCache()),
        rate_limiter=RateLimiter(rpm_limit),
    )


def test_crustdata_client_pins_headers_and_caches(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["x-api-version"] == "2025-11-01"
        return httpx.Response(200, json={"suggestions": ["Acme"]})

    client = build_test_client(handler, monkeypatch)

    first = client.post(
        endpoint="/company/search/autocomplete",
        body={"field": "basic_info.name", "query": "acme", "limit": 10},
        cache_ttl_seconds=60,
    )
    second = client.post(
        endpoint="/company/search/autocomplete",
        body={"field": "basic_info.name", "query": "acme", "limit": 10},
        cache_ttl_seconds=60,
    )

    assert first == second == {"suggestions": ["Acme"]}
    assert calls["count"] == 1


def test_crustdata_client_raises_on_rate_limit(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"suggestions": []})

    client = build_test_client(handler, monkeypatch, rpm_limit=1)

    client.post(
        endpoint="/company/search/autocomplete",
        body={"field": "basic_info.name", "query": "acme-1", "limit": 10},
        cache_ttl_seconds=60,
        bypass_cache=True,
    )

    with pytest.raises(AppError) as exc_info:
        client.post(
            endpoint="/company/search/autocomplete",
            body={"field": "basic_info.name", "query": "acme-2", "limit": 10},
            cache_ttl_seconds=60,
            bypass_cache=True,
        )

    assert exc_info.value.code == "CRUSTDATA_RATE_LIMITED"


def test_crustdata_client_maps_external_errors(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad auth"})

    client = build_test_client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        client.post(
            endpoint="/company/search/autocomplete",
            body={"field": "basic_info.name", "query": "acme", "limit": 10},
            cache_ttl_seconds=60,
        )

    assert exc_info.value.code == "CRUSTDATA_AUTH_FAILED"


def test_crustdata_client_maps_transport_errors(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    client = build_test_client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        client.post(
            endpoint="/company/search/autocomplete",
            body={"field": "basic_info.name", "query": "acme", "limit": 10},
            cache_ttl_seconds=60,
        )

    assert exc_info.value.code == "CRUSTDATA_NETWORK_ERROR"
