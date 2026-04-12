"""tighten constraints: portals.auth_method check + corpus_artifacts uniqueness

Revision ID: 0002_constraints
Revises: 0001_initial
Create Date: 2026-04-12

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_constraints"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AUTH_METHOD_VALUES = ("clave", "certificate", "dnie", "none")
_PORTAL_AUTH_CHECK = f"auth_method IN ({', '.join(repr(v) for v in _AUTH_METHOD_VALUES)})"


def upgrade() -> None:
    """Add check constraint on portals.auth_method and a unique key on corpus_artifacts."""
    with op.batch_alter_table("portals", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_portals_auth_method", _PORTAL_AUTH_CHECK)

    with op.batch_alter_table("corpus_artifacts", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_corpus_artifacts_identity",
            ["year", "modelo_id", "file_path"],
        )


def downgrade() -> None:
    """Drop the constraints added in :func:`upgrade`."""
    with op.batch_alter_table("corpus_artifacts", schema=None) as batch_op:
        batch_op.drop_constraint("uq_corpus_artifacts_identity", type_="unique")

    with op.batch_alter_table("portals", schema=None) as batch_op:
        batch_op.drop_constraint("ck_portals_auth_method", type_="check")
