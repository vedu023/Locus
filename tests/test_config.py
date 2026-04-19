import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults_are_usable():
    settings = Settings()

    assert settings.app_name == "Locus API"
    assert settings.auth_mode == "dev"
    assert settings.crustdata_api_version == "2025-11-01"


def test_settings_reject_invalid_environment():
    with pytest.raises(ValidationError):
        Settings(env="invalid")
