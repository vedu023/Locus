"""Phase 3 geo columns.

Revision ID: 20260419_0003
Revises: 20260419_0002
Create Date: 2026-04-19 14:15:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0003"
down_revision = "20260419_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("point_geojson", sa.JSON(), nullable=True))
    op.add_column(
        "locations",
        sa.Column(
            "geocode_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "locations",
        sa.Column("geocode_precision", sa.String(length=32), nullable=True),
    )
    op.add_column("locations", sa.Column("geocode_error", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_locations_geocode_precision"),
        "locations",
        ["geocode_precision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_locations_geocode_status"),
        "locations",
        ["geocode_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_locations_geocode_status"), table_name="locations")
    op.drop_index(op.f("ix_locations_geocode_precision"), table_name="locations")
    op.drop_column("locations", "geocode_error")
    op.drop_column("locations", "geocode_precision")
    op.drop_column("locations", "geocode_status")
    op.drop_column("locations", "point_geojson")
