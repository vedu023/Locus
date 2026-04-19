"""phase 8 usage events

Revision ID: 20260419_0004
Revises: 20260419_0003
Create Date: 2026-04-19 13:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260419_0004"
down_revision = "20260419_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("auth_provider_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_events_auth_provider_id", "usage_events", ["auth_provider_id"])
    op.create_index("ix_usage_events_action", "usage_events", ["action"])
    op.create_index("ix_usage_events_target_id", "usage_events", ["target_id"])
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_target_id", table_name="usage_events")
    op.drop_index("ix_usage_events_action", table_name="usage_events")
    op.drop_index("ix_usage_events_auth_provider_id", table_name="usage_events")
    op.drop_table("usage_events")
