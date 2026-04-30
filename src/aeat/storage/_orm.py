"""Internal SQLAlchemy ORM mapper classes.

These classes back the declarative schema consumed by Alembic autogenerate.
They are intentionally kept out of the :mod:`aeat.storage` public API — the
public surface exposes pydantic v2 records (see :mod:`aeat.storage.records`)
and repositories bridge between the two.

Note:
    Translatable columns (e.g. modelo names, portal labels) are plain ``str``
    today. Once the trilingual primitive from issue #20 lands, these columns
    will be migrated to the shared ``Translatable`` shape. Each such column
    carries an inline ``TODO(#20)`` marker.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ._encrypted_columns import EncryptedString


class Base(DeclarativeBase):
    """Declarative base for every ORM mapper class in this package."""


class ModeloRow(Base):
    """Row in the ``modelos`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key (e.g. ``MODELO_130``).
        name: Human-readable modelo name.
    """

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # TODO(#20): replace with Translatable once the i18n primitive lands.
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class PortalRow(Base):
    """Row in the ``portals`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key (e.g. ``SEDE_ELECTRONICA_ROOT``).
        base_url: Canonical URL for the portal.
        auth_method: Authentication method as a short string code.
        modelo_id: Optional foreign key to :class:`ModeloRow`.
    """

    __tablename__ = "portals"
    __table_args__ = (
        CheckConstraint(
            "auth_method IN ('clave', 'certificate', 'dnie', 'none')",
            name="ck_portals_auth_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(32), nullable=False)
    modelo_id: Mapped[int | None] = mapped_column(
        ForeignKey("modelos.id", ondelete="SET NULL"),
        nullable=True,
    )
    # TODO(#20): replace with Translatable once the i18n primitive lands.
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    modelo: Mapped[ModeloRow | None] = relationship("ModeloRow", lazy="joined")


class CorpusArtifactRow(Base):
    """Row in the ``corpus_artifacts`` table.

    Attributes:
        id: Surrogate integer primary key.
        year: Tax year this artifact belongs to.
        modelo_id: Foreign key to the owning :class:`ModeloRow`.
        file_path: Project-relative path to the on-disk artifact.
        sha256: Hex digest of the artifact bytes.
        source_url: URL the artifact was fetched from.
        fetched_at: Timestamp when the artifact was fetched (UTC).
    """

    __tablename__ = "corpus_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "modelo_id",
            "file_path",
            name="uq_corpus_artifacts_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    modelo_id: Mapped[int] = mapped_column(
        ForeignKey("modelos.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    modelo: Mapped[ModeloRow] = relationship("ModeloRow", lazy="joined")


_RENTAL_USE_TYPE_VALUES = (
    "VIVIENDA_ARRENDADA",
    "VIVIENDA_HABITUAL",
    "OTRO_INMUEBLE_NO_AFECTO",
    "LOCAL_COMERCIAL",
    "VIVIENDA_DESOCUPADA",
)

_RENTAL_EXPENSE_CATEGORY_VALUES = (
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


def _enum_check(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(repr(v) for v in values) + ")"


class RentalFincaRow(Base):
    """Row in the ``rental_fincas`` table.

    Models one Spanish urban property tracked under #454. Address is
    encrypted at rest because finca addresses identify the contribuyente
    (Catastro stable reference) and qualify as personal data under GDPR.
    """

    __tablename__ = "rental_fincas"
    __table_args__ = (
        CheckConstraint(
            f"use_type IN {_enum_check(_RENTAL_USE_TYPE_VALUES)}",
            name="ck_rental_fincas_use_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(EncryptedString(), nullable=False)
    valor_catastral_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    valor_catastral_construccion: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    valor_catastral_revision_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coste_adquisicion: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    coste_adquisicion_construccion: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date(), nullable=False)
    disposal_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    use_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_stressed_area: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")


class RentalContractRow(Base):
    """Row in the ``rental_contracts`` table.

    Per-contract metadata used by the LIRPF art. 23.2 tier resolver.
    Tenant identifying fields (when added by future schema versions)
    will use :class:`EncryptedString`. The current schema models
    only counts and flags so the row itself is not PII-bearing.
    """

    __tablename__ = "rental_contracts"
    __table_args__ = (
        CheckConstraint(
            "tenant_count >= 1",
            name="ck_rental_contracts_tenant_count_positive",
        ),
        CheckConstraint(
            "qualifying_co_tenant_count >= 0",
            name="ck_rental_contracts_qualifying_share_nonneg",
        ),
        CheckConstraint(
            "qualifying_co_tenant_count <= tenant_count",
            name="ck_rental_contracts_qualifying_share_bounded",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finca_id: Mapped[int] = mapped_column(
        ForeignKey("rental_fincas.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_celebration_date: Mapped[date] = mapped_column(Date(), nullable=False)
    contract_termination_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    tenant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    qualifying_co_tenant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_min_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tenant_max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tenant_is_public_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tenant_is_ley_49_2002_entity_with_social_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tenant_is_imv_beneficiary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dwelling_in_public_program: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prior_contract_last_rent: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    prior_contract_indexation: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    initial_rent: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_first_rental: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rehabilitation_finished_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    lau_17_6_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")

    finca: Mapped[RentalFincaRow] = relationship("RentalFincaRow", lazy="joined")


class RentalIncomeRecordRow(Base):
    """Row in the ``rental_income_records`` table.

    Per-contract per-period gross-rent ledger. The (contract_id,
    period_year) tuple is unique so each contract surfaces a single
    income record per ejercicio.
    """

    __tablename__ = "rental_income_records"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "period_year",
            name="uq_rental_income_records_identity",
        ),
        CheckConstraint(
            "dias_alquilados >= 0 AND dias_alquilados <= 366",
            name="ck_rental_income_records_dias_alquilados_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("rental_contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_rent_received: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    dias_alquilados: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")

    contract: Mapped[RentalContractRow] = relationship("RentalContractRow", lazy="joined")


class RentalExpenseRow(Base):
    """Row in the ``rental_expenses`` table.

    Per-finca per-period categorised expense surface for the LIRPF
    art. 23.1 deductible-gasto rollup.
    """

    __tablename__ = "rental_expenses"
    __table_args__ = (
        CheckConstraint(
            f"category IN {_enum_check(_RENTAL_EXPENSE_CATEGORY_VALUES)}",
            name="ck_rental_expenses_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finca_id: Mapped[int] = mapped_column(
        ForeignKey("rental_fincas.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")

    finca: Mapped[RentalFincaRow] = relationship("RentalFincaRow", lazy="joined")


class RentalAmortizationLedgerRow(Base):
    """Row in the ``rental_amortization_ledger`` table.

    Per-finca per-period art. 23.1.f amortización 3 % accrual with
    cumulative-through-year tracking. The (finca_id, period_year)
    tuple is unique so the ledger has one canonical entry per
    finca per ejercicio.
    """

    __tablename__ = "rental_amortization_ledger"
    __table_args__ = (
        UniqueConstraint(
            "finca_id",
            "period_year",
            name="uq_rental_amortization_ledger_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finca_id: Mapped[int] = mapped_column(
        ForeignKey("rental_fincas.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_alquilados: Mapped[int] = mapped_column(Integer, nullable=False)
    basis_used: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cumulative_amortization_through_year: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")

    finca: Mapped[RentalFincaRow] = relationship("RentalFincaRow", lazy="joined")


metadata = Base.metadata
"""Alembic ``target_metadata`` for autogenerate."""
