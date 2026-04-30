"""rental register: fincas, contracts, income, expenses, amortization ledger (#454)

Revision ID: 0003_rental_register
Revises: 0002_constraints
Create Date: 2026-04-29

Adds the per-finca + per-contract + per-period income / expense /
amortization-ledger schema introduced by #454. Address column on
``rental_fincas`` is encrypted at rest via ``EncryptedString``;
this migration declares its underlying SQLAlchemy storage type
(``LargeBinary``) explicitly because Alembic op-stage code runs
without the ORM type-decorator hierarchy in scope.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_rental_register"
down_revision: str | None = "0002_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_USE_TYPE_VALUES = (
    "VIVIENDA_ARRENDADA",
    "VIVIENDA_HABITUAL",
    "OTRO_INMUEBLE_NO_AFECTO",
    "LOCAL_COMERCIAL",
    "VIVIENDA_DESOCUPADA",
)
_USE_TYPE_CHECK = "use_type IN (" + ", ".join(repr(v) for v in _USE_TYPE_VALUES) + ")"

_EXPENSE_CATEGORY_VALUES = (
    "FINANCIACION_INTERESES",
    "CONSERVACION_REPARACION",
    "IBI_TRIBUTOS_NO_ESTATALES",
    "COMUNIDAD",
    "SEGUROS",
    "SUMINISTROS",
    "ADMINISTRACION_PORTERIA_VIGILANCIA",
    "FORMALIZACION_CONTRATO",
    "DEFENSA_JURIDICA",
    "SALDOS_DUDOSO_COBRO",
    "OTROS",
)
_EXPENSE_CATEGORY_CHECK = "category IN (" + ", ".join(repr(v) for v in _EXPENSE_CATEGORY_VALUES) + ")"


def upgrade() -> None:
    """Create the rental-register schema."""
    op.create_table(
        "rental_fincas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identifier", sa.String(length=64), nullable=False),
        sa.Column("address", sa.LargeBinary(), nullable=False),
        sa.Column("valor_catastral_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("valor_catastral_construccion", sa.Numeric(15, 2), nullable=False),
        sa.Column("valor_catastral_revision_year", sa.Integer(), nullable=True),
        sa.Column("coste_adquisicion", sa.Numeric(15, 2), nullable=False),
        sa.Column("coste_adquisicion_construccion", sa.Numeric(15, 2), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=True),
        sa.Column("use_type", sa.String(length=32), nullable=False),
        sa.Column("is_stressed_area", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default=sa.text("'1'")),
        sa.UniqueConstraint("identifier", name="uq_rental_fincas_identifier"),
        sa.CheckConstraint(_USE_TYPE_CHECK, name="ck_rental_fincas_use_type"),
    )

    op.create_table(
        "rental_contracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("finca_id", sa.Integer(), nullable=False),
        sa.Column("contract_celebration_date", sa.Date(), nullable=False),
        sa.Column("contract_termination_date", sa.Date(), nullable=True),
        sa.Column("tenant_count", sa.Integer(), nullable=False),
        sa.Column("qualifying_co_tenant_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tenant_min_age", sa.Integer(), nullable=True),
        sa.Column("tenant_max_age", sa.Integer(), nullable=True),
        sa.Column("tenant_is_public_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "tenant_is_ley_49_2002_entity_with_social_use",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("tenant_is_imv_beneficiary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dwelling_in_public_program", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prior_contract_last_rent", sa.Numeric(15, 2), nullable=True),
        sa.Column("prior_contract_indexation", sa.Numeric(8, 4), nullable=True),
        sa.Column("initial_rent", sa.Numeric(15, 2), nullable=False),
        sa.Column("is_first_rental", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rehabilitation_finished_date", sa.Date(), nullable=True),
        sa.Column("lau_17_6_compliant", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default=sa.text("'1'")),
        sa.ForeignKeyConstraint(
            ["finca_id"],
            ["rental_fincas.id"],
            name="fk_rental_contracts_finca_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("tenant_count >= 1", name="ck_rental_contracts_tenant_count_positive"),
        sa.CheckConstraint(
            "qualifying_co_tenant_count >= 0",
            name="ck_rental_contracts_qualifying_share_nonneg",
        ),
        sa.CheckConstraint(
            "qualifying_co_tenant_count <= tenant_count",
            name="ck_rental_contracts_qualifying_share_bounded",
        ),
    )

    op.create_table(
        "rental_income_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("gross_rent_received", sa.Numeric(15, 2), nullable=False),
        sa.Column("dias_alquilados", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default=sa.text("'1'")),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["rental_contracts.id"],
            name="fk_rental_income_records_contract_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "contract_id",
            "period_year",
            name="uq_rental_income_records_identity",
        ),
        sa.CheckConstraint(
            "dias_alquilados >= 0 AND dias_alquilados <= 366",
            name="ck_rental_income_records_dias_alquilados_range",
        ),
    )

    op.create_table(
        "rental_expenses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("finca_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default=sa.text("'1'")),
        sa.ForeignKeyConstraint(
            ["finca_id"],
            ["rental_fincas.id"],
            name="fk_rental_expenses_finca_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(_EXPENSE_CATEGORY_CHECK, name="ck_rental_expenses_category"),
    )

    op.create_table(
        "rental_amortization_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("finca_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("dias_alquilados", sa.Integer(), nullable=False),
        sa.Column("basis_used", sa.Numeric(15, 2), nullable=False),
        sa.Column("amortization_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("cumulative_amortization_through_year", sa.Numeric(15, 2), nullable=False),
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default=sa.text("'1'")),
        sa.ForeignKeyConstraint(
            ["finca_id"],
            ["rental_fincas.id"],
            name="fk_rental_amortization_ledger_finca_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "finca_id",
            "period_year",
            name="uq_rental_amortization_ledger_identity",
        ),
    )


def downgrade() -> None:
    """Drop the rental-register schema in reverse FK-dependency order."""
    op.drop_table("rental_amortization_ledger")
    op.drop_table("rental_expenses")
    op.drop_table("rental_income_records")
    op.drop_table("rental_contracts")
    op.drop_table("rental_fincas")
