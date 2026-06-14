"""Internal SQLAlchemy ORM mapper classes.

Backs the declarative schema consumed by Alembic autogenerate.
Intentionally kept out of the :mod:`aeat.adapters.persistence.storage`
public API: the public surface exposes pydantic v2 records (see
:mod:`aeat.adapters.persistence.storage.sql.records`) and the
per-domain repositories bridge between the ORM rows and the typed
records.
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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..crypto._encrypted_columns import EncryptedString, HashedLookup

_HASH_HEX_LENGTH = 64


def _nullable_fixed_length_check(column_name: str, expected_length: int) -> CheckConstraint:
    return CheckConstraint(
        f"{column_name} IS NULL OR length({column_name}) = {expected_length}",
        name=f"ck_secure_objects_{column_name}_len",
    )


class Base(DeclarativeBase):
    """Declarative base for every ORM mapper class in this package."""


class ModeloRow(Base):
    """Row in the ``modelos`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key for the modelo record.
        name: Human-readable modelo name.
    """

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class PortalOrmRow(Base):
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


class SecureObjectRow(Base):
    """Encrypted byte-object row for sensitive application payloads.

    Domain repositories use this table for financial catalogues and
    workflow state that must not land as standalone JSON files. The
    ``payload`` column is a SQL BLOB holding the AEAD wire bytes; the
    repository encrypts and decrypts it explicitly (rather than through a
    column ``TypeDecorator``) so the row identity (``namespace`` +
    ``object_key`` digest + ``schema_version``) can be bound into the AEAD
    associated data, making a ciphertext refuse to decrypt under any other
    row. The remaining fields are routing, revision-lineage, and integrity
    metadata.
    """

    __tablename__ = "secure_objects"
    __table_args__ = (
        UniqueConstraint(
            "namespace",
            "object_key",
            name="uq_secure_objects_identity",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name="ck_secure_objects_schema_version_positive",
        ),
        _nullable_fixed_length_check("revision_id", _HASH_HEX_LENGTH),
        _nullable_fixed_length_check("previous_revision_id", _HASH_HEX_LENGTH),
        _nullable_fixed_length_check("previous_payload_hash", _HASH_HEX_LENGTH),
        _nullable_fixed_length_check("payload_hash", _HASH_HEX_LENGTH),
        _nullable_fixed_length_check("ciphertext_hash", _HASH_HEX_LENGTH),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[bytes] = mapped_column(HashedLookup(), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_ancestor_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ciphertext_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    write_provenance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conflict_policy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


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


class FincaRow(Base):
    """Row in the ``rental_fincas`` table.

    Models one Spanish urban property. The address column is encrypted
    at rest via :class:`aeat.adapters.persistence.storage.crypto.EncryptedString`
    because finca addresses identify the contribuyente through the
    Catastro stable reference and qualify as personal data under GDPR.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key for the finca.
        address: Encrypted street address.
        valor_catastral_total: Total Catastro value (land + construction).
        valor_catastral_construccion: Catastro value of the construction
            component, used as the LIRPF art. 23.1.f amortization basis.
        valor_catastral_revision_year: Year of the most recent Catastro
            revision; ``None`` when unavailable.
        coste_adquisicion: Total acquisition cost.
        coste_adquisicion_construccion: Acquisition cost attributable to
            the construction component (alternative amortization basis).
        acquisition_date: Date the property was acquired.
        disposal_date: Date the property was sold or otherwise disposed
            of, when applicable.
        use_type: Closed enum: ``VIVIENDA_ARRENDADA`` /
            ``VIVIENDA_HABITUAL`` / ``OTRO_INMUEBLE_NO_AFECTO`` /
            ``LOCAL_COMERCIAL`` / ``VIVIENDA_DESOCUPADA``.
        is_stressed_area: Whether the finca sits in a declared
            stressed-rent area for LIRPF art. 23.2 tier resolution.
        schema_version: Per-row schema version; defaults to ``"1"``.
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


class ArrendamientoRow(Base):
    """Row in the ``rental_contracts`` table.

    Per-contract metadata used by the LIRPF art. 23.2 tier resolver.
    Tenant identifying fields, when added by future schema versions,
    will use :class:`aeat.adapters.persistence.storage.crypto.EncryptedString`.
    The current schema models only counts and flags so the row itself
    is not PII-bearing.

    Attributes:
        id: Surrogate integer primary key.
        finca_id: Foreign key into :class:`FincaRow`.
        contract_celebration_date: Date the contract was signed.
        contract_termination_date: Date the contract terminated, when
            applicable.
        tenant_count: Total tenants on the contract.
        qualifying_co_tenant_count: Subset of tenants that qualify for
            the LIRPF art. 23.2 reduction.
        tenant_min_age: Minimum tenant age, when known.
        tenant_max_age: Maximum tenant age, when known.
        tenant_is_public_admin: True when the tenant is a public
            administration body.
        tenant_is_ley_49_2002_entity_with_social_use: Ley 49/2002 social-
            use qualifier.
        tenant_is_imv_beneficiary: Ingreso Mínimo Vital beneficiary flag.
        dwelling_in_public_program: Public housing program qualifier.
        prior_contract_last_rent: Last rent under the previous contract,
            when known.
        prior_contract_indexation: Indexation factor applied to the
            previous contract.
        initial_rent: Initial monthly rent under the new contract.
        is_first_rental: True when the dwelling has never been rented
            before.
        rehabilitation_finished_date: Date a qualifying rehabilitation
            completed, when applicable.
        lau_17_6_compliant: True when the contract complies with the
            Ley de Arrendamientos Urbanos art. 17.6.
        schema_version: Per-row schema version; defaults to ``"1"``.
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

    finca: Mapped[FincaRow] = relationship("FincaRow", lazy="joined")


class FincaRendimientoRecordRow(Base):
    """Row in the ``rental_income_records`` table.

    Per-contract per-period gross-rent ledger. The
    ``(contract_id, period_year)`` tuple is unique so each contract
    surfaces a single income record per ejercicio.

    Attributes:
        id: Surrogate integer primary key.
        contract_id: Foreign key into :class:`ArrendamientoRow`.
        period_year: Tax year the income belongs to.
        gross_rent_received: Gross rent received during the period.
        dias_alquilados: Days the property was actually rented during
            the period (0..366).
        schema_version: Per-row schema version; defaults to ``"1"``.
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

    contract: Mapped[ArrendamientoRow] = relationship("ArrendamientoRow", lazy="joined")


class FincaGastoRow(Base):
    """Row in the ``rental_expenses`` table.

    Per-finca per-period categorised expense surface for the LIRPF
    art. 23.1 deductible-gasto rollup.

    Attributes:
        id: Surrogate integer primary key.
        finca_id: Foreign key into :class:`FincaRow`.
        period_year: Tax year the expense belongs to.
        category: One of the closed expense categories
            (``FINANCIACION_INTERESES``, ``CONSERVACION_REPARACION``,
            ``IBI_TRIBUTOS_NO_ESTATALES``, ``COMUNIDAD``, ``SEGUROS``,
            ``SUMINISTROS``, ``ADMINISTRACION_PORTERIA_VIGILANCIA``,
            ``FORMALIZACION_CONTRATO``, ``DEFENSA_JURIDICA``,
            ``SALDOS_DUDOSO_COBRO``, ``OTROS``).
        amount: Expense amount.
        schema_version: Per-row schema version; defaults to ``"1"``.
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

    finca: Mapped[FincaRow] = relationship("FincaRow", lazy="joined")


class FincaAmortizacionLedgerRow(Base):
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

    finca: Mapped[FincaRow] = relationship("FincaRow", lazy="joined")


metadata = Base.metadata
"""Alembic ``target_metadata`` for autogenerate."""
