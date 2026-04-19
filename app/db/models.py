from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def generate_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    auth_provider_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    search_runs: Mapped[list["SearchRun"]] = relationship(back_populates="user")
    watchlists: Mapped[list["Watchlist"]] = relationship(back_populates="user")


class Location(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    location_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    raw_label: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    point_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    geocode_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    geocode_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geocode_precision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    geocode_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    crustdata_company_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    name: Mapped[str] = mapped_column(Text)
    primary_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    professional_network_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    company_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year_founded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_count_range: Mapped[str | None] = mapped_column(String(64), nullable=True)
    funding_total_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_last_round_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    funding_last_round_amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hq_location_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("locations.id"),
        nullable=True,
        index=True,
    )
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    hq_location: Mapped[Location | None] = relationship()


class Person(TimestampMixin, Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    crustdata_person_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    professional_network_url: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_title: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    current_company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id"),
        nullable=True,
        index=True,
    )
    seniority_level: Mapped[str | None] = mapped_column(String(128), nullable=True)
    function_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("locations.id"),
        nullable=True,
        index=True,
    )
    has_business_email: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_personal_email: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_phone_number: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    current_company: Mapped[Company | None] = relationship()
    location: Mapped[Location | None] = relationship()


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    lens: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_payload: Mapped[dict] = mapped_column("input", JSON, default=dict)
    normalized_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    cost_estimate: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="search_runs")
    entities: Mapped[list["SearchRunEntity"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class SearchRunEntity(Base):
    __tablename__ = "search_run_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_runs.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    person_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("people.id"), nullable=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("locations.id"),
        nullable=True,
        index=True,
    )
    lens_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[SearchRun] = relationship(back_populates="entities")
    company: Mapped[Company | None] = relationship()
    person: Mapped[Person | None] = relationship()
    location: Mapped[Location | None] = relationship()


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    person_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("people.id"), nullable=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id"), nullable=True
    )
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    lens: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    watchlist_id: Mapped[str] = mapped_column(String(36), ForeignKey("watchlists.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    person_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("people.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")


class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(255), index=True)
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    status_code: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


__all__ = [
    "ApiCache",
    "Base",
    "Company",
    "Location",
    "Person",
    "SearchRun",
    "SearchRunEntity",
    "Signal",
    "User",
    "Watchlist",
    "WatchlistItem",
]
