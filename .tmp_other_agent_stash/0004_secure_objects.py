"""secure objects: encrypted application byte payloads

Revision ID: 0004_secure_objects
Revises: 0003_rental_register
Create Date: 2026-05-05

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_secure_objects"
down_revision: str | None = "0003_rental_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the encrypted byte-object table."""

    op.create_table(
        "secure_objects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=256), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("namespace", "object_key", name="uq_secure_objects_identity"),
    )


def downgrade() -> None:
    """Drop the encrypted byte-object table."""

    op.drop_table("secure_objects")

