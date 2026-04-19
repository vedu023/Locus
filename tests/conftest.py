import os

os.environ.setdefault("LOCUS_ENV", "test")
os.environ.setdefault("LOCUS_DEBUG", "false")
os.environ.setdefault("LOCUS_GEOCODER_PROVIDER", "noop")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import pytest
from fastapi.testclient import TestClient

import app.db.models  # noqa: F401
from app.api.deps import get_geocoder
from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.db.base import Base
from app.db.session import get_engine, get_session_factory
from app.main import app


@pytest.fixture(autouse=True)
def clear_caches():
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_redis_client.cache_clear()
    get_geocoder.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_redis_client.cache_clear()
    get_geocoder.cache_clear()


@pytest.fixture(autouse=True)
def db_schema():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def api_app():
    return app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
