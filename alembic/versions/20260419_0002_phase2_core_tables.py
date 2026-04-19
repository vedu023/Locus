"""Phase 2 core tables.

Revision ID: 20260419_0002
Revises: 20260419_0001
Create Date: 2026-04-19 12:30:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0002"
down_revision = "20260419_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("auth_provider_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_auth_provider_id"), "users", ["auth_provider_id"], unique=True)

    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("location_key", sa.String(length=512), nullable=False),
        sa.Column("raw_label", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geocode_provider", sa.String(length=64), nullable=True),
        sa.Column("geocode_confidence", sa.Float(), nullable=True),
        sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_locations_location_key"), "locations", ["location_key"], unique=True)

    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("crustdata_company_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("primary_domain", sa.String(length=255), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("professional_network_url", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("company_type", sa.String(length=64), nullable=True),
        sa.Column("year_founded", sa.Integer(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("employee_count_range", sa.String(length=64), nullable=True),
        sa.Column("funding_total_usd", sa.Float(), nullable=True),
        sa.Column("funding_last_round_type", sa.String(length=64), nullable=True),
        sa.Column("funding_last_round_amount_usd", sa.Float(), nullable=True),
        sa.Column("funding_last_date", sa.Date(), nullable=True),
        sa.Column("hq_location_id", sa.String(length=36), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hq_location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crustdata_company_id"),
    )
    op.create_index(
        op.f("ix_companies_primary_domain"), "companies", ["primary_domain"], unique=False
    )
    op.create_index(op.f("ix_companies_industry"), "companies", ["industry"], unique=False)
    op.create_index(
        op.f("ix_companies_hq_location_id"), "companies", ["hq_location_id"], unique=False
    )

    op.create_table(
        "people",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("crustdata_person_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("professional_network_url", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("current_title", sa.Text(), nullable=True),
        sa.Column("current_company_name", sa.Text(), nullable=True),
        sa.Column("current_company_domain", sa.String(length=255), nullable=True),
        sa.Column("current_company_id", sa.String(length=36), nullable=True),
        sa.Column("seniority_level", sa.String(length=128), nullable=True),
        sa.Column("function_category", sa.String(length=128), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("has_business_email", sa.Boolean(), nullable=True),
        sa.Column("has_personal_email", sa.Boolean(), nullable=True),
        sa.Column("has_phone_number", sa.Boolean(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["current_company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crustdata_person_id"),
        sa.UniqueConstraint("professional_network_url"),
    )
    op.create_index(
        op.f("ix_people_current_company_id"), "people", ["current_company_id"], unique=False
    )
    op.create_index(op.f("ix_people_current_title"), "people", ["current_title"], unique=False)
    op.create_index(op.f("ix_people_location_id"), "people", ["location_id"], unique=False)

    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lens", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("normalized_filters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_counts", sa.JSON(), nullable=False),
        sa.Column("cost_estimate", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_search_runs_lens"), "search_runs", ["lens"], unique=False)
    op.create_index(op.f("ix_search_runs_status"), "search_runs", ["status"], unique=False)
    op.create_index(op.f("ix_search_runs_user_id"), "search_runs", ["user_id"], unique=False)

    op.create_table(
        "search_run_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("person_id", sa.String(length=36), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("lens_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["search_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_search_run_entities_entity_type"),
        "search_run_entities",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_run_entities_location_id"),
        "search_run_entities",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_run_entities_run_id"), "search_run_entities", ["run_id"], unique=False
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("person_id", sa.String(length=36), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signals_entity_type"), "signals", ["entity_type"], unique=False)
    op.create_index(op.f("ix_signals_signal_type"), "signals", ["signal_type"], unique=False)

    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lens", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watchlists_user_id"), "watchlists", ["user_id"], unique=False)

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("watchlist_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("person_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_watchlist_items_entity_type"), "watchlist_items", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_watchlist_items_watchlist_id"), "watchlist_items", ["watchlist_id"], unique=False
    )

    op.create_table(
        "api_cache",
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=255), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index(op.f("ix_api_cache_expires_at"), "api_cache", ["expires_at"], unique=False)
    op.create_index(op.f("ix_api_cache_provider"), "api_cache", ["provider"], unique=False)
    op.create_index(op.f("ix_api_cache_request_hash"), "api_cache", ["request_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_cache_request_hash"), table_name="api_cache")
    op.drop_index(op.f("ix_api_cache_provider"), table_name="api_cache")
    op.drop_index(op.f("ix_api_cache_expires_at"), table_name="api_cache")
    op.drop_table("api_cache")

    op.drop_index(op.f("ix_watchlist_items_watchlist_id"), table_name="watchlist_items")
    op.drop_index(op.f("ix_watchlist_items_entity_type"), table_name="watchlist_items")
    op.drop_table("watchlist_items")

    op.drop_index(op.f("ix_watchlists_user_id"), table_name="watchlists")
    op.drop_table("watchlists")

    op.drop_index(op.f("ix_signals_signal_type"), table_name="signals")
    op.drop_index(op.f("ix_signals_entity_type"), table_name="signals")
    op.drop_table("signals")

    op.drop_index(op.f("ix_search_run_entities_run_id"), table_name="search_run_entities")
    op.drop_index(op.f("ix_search_run_entities_location_id"), table_name="search_run_entities")
    op.drop_index(op.f("ix_search_run_entities_entity_type"), table_name="search_run_entities")
    op.drop_table("search_run_entities")

    op.drop_index(op.f("ix_search_runs_user_id"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_status"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_lens"), table_name="search_runs")
    op.drop_table("search_runs")

    op.drop_index(op.f("ix_people_location_id"), table_name="people")
    op.drop_index(op.f("ix_people_current_title"), table_name="people")
    op.drop_index(op.f("ix_people_current_company_id"), table_name="people")
    op.drop_table("people")

    op.drop_index(op.f("ix_companies_hq_location_id"), table_name="companies")
    op.drop_index(op.f("ix_companies_industry"), table_name="companies")
    op.drop_index(op.f("ix_companies_primary_domain"), table_name="companies")
    op.drop_table("companies")

    op.drop_index(op.f("ix_locations_location_key"), table_name="locations")
    op.drop_table("locations")

    op.drop_index(op.f("ix_users_auth_provider_id"), table_name="users")
    op.drop_table("users")
