from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Locus API", alias="LOCUS_APP_NAME")
    env: Literal["development", "test", "production"] = Field(
        default="development",
        alias="LOCUS_ENV",
    )
    debug: bool = Field(default=True, alias="LOCUS_DEBUG")
    host: str = Field(default="0.0.0.0", alias="LOCUS_HOST")
    port: int = Field(default=8000, alias="LOCUS_PORT")
    log_level: str = Field(default="INFO", alias="LOCUS_LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/locus",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    auth_mode: Literal["dev", "disabled"] = Field(default="dev", alias="LOCUS_AUTH_MODE")
    dev_user_id: str = Field(default="dev-user", alias="LOCUS_DEV_USER_ID")
    dev_user_email: str = Field(default="dev@locus.local", alias="LOCUS_DEV_USER_EMAIL")

    crustdata_api_key: str | None = Field(default=None, alias="CRUSTDATA_API_KEY")
    crustdata_api_base_url: str = Field(
        default="https://api.crustdata.com",
        alias="CRUSTDATA_API_BASE_URL",
    )
    crustdata_api_version: str = Field(
        default="2025-11-01",
        alias="CRUSTDATA_API_VERSION",
    )
    crustdata_rpm_limit: int = Field(default=12, alias="CRUSTDATA_RPM_LIMIT")
    crustdata_timeout_seconds: float = Field(default=30.0, alias="CRUSTDATA_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
