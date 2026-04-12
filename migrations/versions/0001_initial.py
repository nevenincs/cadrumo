"""initial schema: modelos, portals, corpus_artifacts

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the first-cut tables."""
    op.create_table(
        "modelos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identifier", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("identifier", name="uq_modelos_identifier"),
    )
    op.create_table(
        "portals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identifier", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("auth_method", sa.String(length=32), nullable=False),
        sa.Column("modelo_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("identifier", name="uq_portals_identifier"),
        sa.ForeignKeyConstraint(
            ["modelo_id"],
            ["modelos.id"],
            name="fk_portals_modelo_id",
            ondelete="SET NULL",
        ),
    )
    op.create_table(
        "corpus_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("modelo_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["modelo_id"],
            ["modelos.id"],
            name="fk_corpus_artifacts_modelo_id",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Drop the first-cut tables in reverse dependency order."""
    op.drop_table("corpus_artifacts")
    op.drop_table("portals")
    op.drop_table("modelos")
