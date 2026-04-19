from __future__ import annotations

import hashlib
import json
import time
from threading import Lock
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError
from app.crustdata.cache import CacheBackend, build_cache_backend
from app.crustdata.errors import normalize_crustdata_error


class RateLimiter:
    def __init__(self, rpm_limit: int) -> None:
        self.rpm_limit = rpm_limit
        self._lock = Lock()
        self._calls: list[float] = []

    def acquire(self) -> None:
        if self.rpm_limit <= 0:
            return

        now = time.monotonic()
        cutoff = now - 60.0

        with self._lock:
            self._calls = [call for call in self._calls if call >= cutoff]
            if len(self._calls) >= self.rpm_limit:
                raise AppError(
                    code="CRUSTDATA_RATE_LIMITED",
                    message="Local Crustdata rate limit exceeded.",
                    status_code=429,
                    details={"provider": "crustdata", "rpm_limit": self.rpm_limit},
                )
            self._calls.append(now)


class CrustdataClient:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        cache_backend: CacheBackend | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.settings = get_settings()
        self.cache_backend = cache_backend or build_cache_backend()
        self.rate_limiter = rate_limiter or RateLimiter(self.settings.crustdata_rpm_limit)
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client(
            base_url=self.settings.crustdata_api_base_url,
            timeout=self.settings.crustdata_timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self.http_client.close()

    def build_cache_key(self, endpoint: str, body: dict[str, Any]) -> str:
        payload = {
            "provider": "crustdata",
            "api_version": self.settings.crustdata_api_version,
            "endpoint": endpoint,
            "body": body,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"crustdata:{digest}"

    def post(
        self,
        *,
        endpoint: str,
        body: dict[str, Any],
        cache_ttl_seconds: int,
        bypass_cache: bool = False,
    ) -> dict[str, Any]:
        if not self.settings.crustdata_api_key:
            raise AppError(
                code="CONFIGURATION_ERROR",
                message="CRUSTDATA_API_KEY is not configured.",
                status_code=500,
            )

        cache_key = self.build_cache_key(endpoint, body)

        if not bypass_cache:
            cached = self.cache_backend.get(cache_key)
            if cached is not None:
                return cached

        self.rate_limiter.acquire()

        response = self.http_client.post(
            endpoint,
            headers={
                "authorization": f"Bearer {self.settings.crustdata_api_key}",
                "content-type": "application/json",
                "x-api-version": self.settings.crustdata_api_version,
            },
            json=body,
        )

        try:
            payload = response.json()
        except Exception:
            payload = {"raw_text": response.text}

        if not response.is_success:
            raise normalize_crustdata_error(response.status_code, payload, endpoint)

        if not isinstance(payload, dict):
            raise AppError(
                code="CRUSTDATA_BAD_RESPONSE",
                message="Crustdata response payload must be a JSON object.",
                status_code=502,
                details={"endpoint": endpoint},
            )

        self.cache_backend.set(cache_key, payload, cache_ttl_seconds)
        return payload
