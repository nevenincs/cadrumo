"""Internal SQLAlchemy ORM mapper classes.

Backs the declarative schema consumed by Alembic autogenerate.
Intentionally kept out of the :mod:`adapters.persistence.storage`
public API: the public surface exposes pydantic v2 records (see
:mod:`adapters.persistence.storage.sql.records`) and the
per-domain repositories bridge between the ORM rows and the typed
records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..crypto.encrypted_columns import EncryptedString, HashedLookup

_HASH_HEX_LENGTH = 64


def _nullable_fixed_length_check(column_name: str, expected_length: int) -> CheckConstraint:
    return CheckConstraint(
        f"{column_name} IS NULL OR length({column_name}) = {expected_length}",
        name=f"ck_secure_objects_{column_name}_len",
    )


class Base(DeclarativeBase):
    """Declarative base for every ORM mapper class in this package."""


# Named `Annotated` column-type aliases shared across mapper classes below.
#
# `mapped_column()` is declared to return `MappedColumn[Any]` (SQLAlchemy relies
# on its mypy plugin, not available here, to narrow that to `Mapped[T]` at the
# assignment site). Folding the `mapped_column(...)` call into the annotation
# itself via `Mapped[Annotated[T, mapped_column(...)]]` -- SQLAlchemy's own
# documented alternative to the assignment form -- makes every attribute a bare
# annotation with no right-hand side, so there is no `MappedColumn[Any]` value
# ever assigned to a `Mapped[T]`-declared name to be unsound.
_intpk = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True)]

_str8 = Annotated[str, mapped_column(String(8), nullable=False)]
_str32 = Annotated[str, mapped_column(String(32), nullable=False)]
_str32_opt = Annotated[str | None, mapped_column(String(32), nullable=True)]
_str48 = Annotated[str, mapped_column(String(48), nullable=False)]
_str64 = Annotated[str, mapped_column(String(64), nullable=False)]
_str64_unique = Annotated[str, mapped_column(String(64), unique=True, nullable=False)]
_str64_opt = Annotated[str | None, mapped_column(String(64), nullable=True)]
_str128 = Annotated[str, mapped_column(String(128), nullable=False)]
_str128_opt = Annotated[str | None, mapped_column(String(128), nullable=True)]
_str255 = Annotated[str, mapped_column(String(255), nullable=False)]
_str255_opt = Annotated[str | None, mapped_column(String(255), nullable=True)]
_str512 = Annotated[str, mapped_column(String(512), nullable=False)]
_str1024 = Annotated[str, mapped_column(String(1024), nullable=False)]
_text_opt = Annotated[str | None, mapped_column(Text, nullable=True)]

_int_required = Annotated[int, mapped_column(Integer, nullable=False)]
_int_opt = Annotated[int | None, mapped_column(Integer, nullable=True)]
_int_default_zero = Annotated[int, mapped_column(Integer, nullable=False, default=0)]

_date_required = Annotated[date, mapped_column(Date(), nullable=False)]
_date_opt = Annotated[date | None, mapped_column(Date(), nullable=True)]
_datetime_tz = Annotated[datetime, mapped_column(DateTime(timezone=True), nullable=False)]
_datetime_tz_opt = Annotated[datetime | None, mapped_column(DateTime(timezone=True), nullable=True)]

_decimal_15_2 = Annotated[Decimal, mapped_column(Numeric(15, 2), nullable=False)]
_decimal_15_2_opt = Annotated[Decimal | None, mapped_column(Numeric(15, 2), nullable=True)]
_decimal_8_4_opt = Annotated[Decimal | None, mapped_column(Numeric(8, 4), nullable=True)]

_bool_default_false = Annotated[bool, mapped_column(Boolean, nullable=False, default=False)]
_bool_default_true = Annotated[bool, mapped_column(Boolean, nullable=False, default=True)]

_large_binary = Annotated[bytes, mapped_column(LargeBinary, nullable=False)]
_hashed_lookup = Annotated[bytes, mapped_column(HashedLookup(), nullable=False)]
_encrypted_string = Annotated[str, mapped_column(EncryptedString(), nullable=False)]

_portal_modelo_fk = Annotated[
    int | None,
    mapped_column(ForeignKey("modelos.id", ondelete="SET NULL"), nullable=True),
]
_corpus_modelo_fk = Annotated[
    int,
    mapped_column(ForeignKey("modelos.id", ondelete="CASCADE"), nullable=False),
]
_finca_fk = Annotated[
    int,
    mapped_column(ForeignKey("rental_fincas.id", ondelete="CASCADE"), nullable=False),
]
_contract_fk = Annotated[
    int,
    mapped_column(ForeignKey("rental_contracts.id", ondelete="CASCADE"), nullable=False),
]


class ModeloRow(Base):
    """Row in the ``modelos`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key for the modelo record.
        name: Human-readable modelo name.
    """

    __tablename__ = "modelos"

    id: Mapped[_intpk]
    identifier: Mapped[_str64_unique]
    name: Mapped[_str255]


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

    id: Mapped[_intpk]
    identifier: Mapped[_str64_unique]
    base_url: Mapped[_str512]
    auth_method: Mapped[_str32]
    modelo_id: Mapped[_portal_modelo_fk]
    label: Mapped[_str255]

    if TYPE_CHECKING:
        modelo: Mapped[ModeloRow | None]
    else:
        modelo = relationship("ModeloRow", lazy="joined")


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

    id: Mapped[_intpk]
    year: Mapped[_int_required]
    modelo_id: Mapped[_corpus_modelo_fk]
    file_path: Mapped[_str1024]
    sha256: Mapped[_str64]
    source_url: Mapped[_str1024]
    fetched_at: Mapped[_datetime_tz]

    if TYPE_CHECKING:
        modelo: Mapped[ModeloRow]
    else:
        modelo = relationship("ModeloRow", lazy="joined")


class TransactionDateIndexRow(Base):
    """Plaintext routing row: one ledger transaction's filing date and year.

    This table is a derived, rebuildable read-side cache co-written atomically
    with :class:`SecureObjectRow` ledger writes (see
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`).
    It exists purely to let a period-scoped ledger read select the candidate
    transaction ids for a date range with a plaintext SQL predicate, so only
    those rows need to be decrypted -- never the whole per-bucket catalogue.

    The row carries ONLY non-sensitive routing keys: the bucket id, the
    transaction id, its filing date (``value_date`` or ``booked_date`` --
    the same field every ledger aggregator already filters on), the filing
    year the date falls in, and the inclusive span of every date the row can
    file an observation under. No amount, counterparty, description,
    NIF, or other financial content may ever be added to this table; it is
    plaintext by design (:class:`~adapters.persistence.storage.SensitivityClass`
    ``CACHE``) and correctness never depends on it being present or fresh --
    a missing or incomplete index falls back to the full encrypted scan.

    Attributes:
        id: Surrogate integer primary key.
        bucket_id: Owning profile bucket, so a shared database never mixes
            two buckets' routing rows.
        transaction_id: The ledger transaction's stable content-derived id.
        filing_date: ``value_date`` or ``booked_date`` (whichever the ledger
            aggregation layer would use) as a plain SQL ``Date``.
        filing_year: ``filing_date.year``, indexed separately so a
            year-scoped candidate-id query does not need a date-range
            predicate at all.
        eligible_from: Earliest date this row can file an observation under,
            per :func:`~domain.transactions.transaction_eligible_date_span`.
            Equal to ``filing_date`` unless an IVA criterio-de-caja timing
            override moves the row's devengo or collection dates off it.
        eligible_to: Latest such date, inclusive. A period-scoped partition
            selects on span OVERLAP rather than on ``filing_date``, so a row
            booked in one quarter that carries a prior-quarter cash-accounting
            devengo is never dropped from the candidate set.
    """

    __tablename__ = "transaction_date_index"
    __table_args__ = (
        UniqueConstraint(
            "bucket_id",
            "transaction_id",
            name="uq_transaction_date_index_identity",
        ),
        Index(
            "ix_transaction_date_index_bucket_date",
            "bucket_id",
            "filing_date",
        ),
        Index(
            "ix_transaction_date_index_bucket_eligible_span",
            "bucket_id",
            "eligible_from",
            "eligible_to",
        ),
    )

    id: Mapped[_intpk]
    bucket_id: Mapped[_str64]
    transaction_id: Mapped[_str64]
    filing_date: Mapped[_date_required]
    filing_year: Mapped[_int_required]
    eligible_from: Mapped[_date_required]
    eligible_to: Mapped[_date_required]


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

    id: Mapped[_intpk]
    namespace: Mapped[_str128]
    object_key: Mapped[_hashed_lookup]
    classification: Mapped[_str32]
    schema_version: Mapped[_int_required]
    written_at: Mapped[_datetime_tz]
    revision_id: Mapped[_str64_opt]
    previous_revision_id: Mapped[_str64_opt]
    revision_ancestor_ids: Mapped[_text_opt]
    previous_payload_hash: Mapped[_str64_opt]
    payload_hash: Mapped[_str64_opt]
    ciphertext_hash: Mapped[_str64_opt]
    revision_written_at: Mapped[_datetime_tz_opt]
    write_provenance: Mapped[_str255_opt]
    source_event_id: Mapped[_str128_opt]
    conflict_policy: Mapped[_str32_opt]
    payload: Mapped[_large_binary]


_RENTAL_USE_TYPE_VALUES = (
    "VIVIENDA_ARRENDADA",
    "VIVIENDA_HABITUAL",
    "OTRO_INMUEBLE_NO_AFECTO",
    "LOCAL_COMERCIAL",
    "VIVIENDA_TURISTICA",
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
    at rest via :class:`~adapters.persistence.storage.crypto.EncryptedString`
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
            ``LOCAL_COMERCIAL`` / ``VIVIENDA_TURISTICA`` / ``VIVIENDA_DESOCUPADA``.
        is_stressed_area: Whether the finca sits in a declared
            stressed-rent area for LIRPF art. 23.2 tier resolution.
        schema_version: Per-row schema version, always copied from the
            domain record; this column declares no default of its own.
    """

    __tablename__ = "rental_fincas"
    __table_args__ = (
        CheckConstraint(
            f"use_type IN {_enum_check(_RENTAL_USE_TYPE_VALUES)}",
            name="ck_rental_fincas_use_type",
        ),
    )

    id: Mapped[_intpk]
    identifier: Mapped[_str64_unique]
    address: Mapped[_encrypted_string]
    valor_catastral_total: Mapped[_decimal_15_2]
    valor_catastral_construccion: Mapped[_decimal_15_2]
    valor_catastral_revision_year: Mapped[_int_opt]
    coste_adquisicion: Mapped[_decimal_15_2]
    coste_adquisicion_construccion: Mapped[_decimal_15_2]
    acquisition_date: Mapped[_date_required]
    disposal_date: Mapped[_date_opt]
    use_type: Mapped[_str32]
    is_stressed_area: Mapped[_bool_default_false]
    schema_version: Mapped[_str8]


class ArrendamientoRow(Base):
    """Row in the ``rental_contracts`` table.

    Per-contract metadata used by the LIRPF art. 23.2 tier resolver.
    Tenant identifying fields, when added by future schema versions,
    will use :class:`~adapters.persistence.storage.crypto.EncryptedString`.
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
        schema_version: Per-row schema version, always copied from the
            domain record; this column declares no default of its own.
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

    id: Mapped[_intpk]
    finca_id: Mapped[_finca_fk]
    contract_celebration_date: Mapped[_date_required]
    contract_termination_date: Mapped[_date_opt]
    tenant_count: Mapped[_int_required]
    qualifying_co_tenant_count: Mapped[_int_default_zero]
    tenant_min_age: Mapped[_int_opt]
    tenant_max_age: Mapped[_int_opt]
    tenant_is_public_admin: Mapped[_bool_default_false]
    tenant_is_ley_49_2002_entity_with_social_use: Mapped[_bool_default_false]
    tenant_is_imv_beneficiary: Mapped[_bool_default_false]
    dwelling_in_public_program: Mapped[_bool_default_false]
    prior_contract_last_rent: Mapped[_decimal_15_2_opt]
    prior_contract_indexation: Mapped[_decimal_8_4_opt]
    initial_rent: Mapped[_decimal_15_2]
    is_first_rental: Mapped[_bool_default_false]
    rehabilitation_finished_date: Mapped[_date_opt]
    lau_17_6_compliant: Mapped[_bool_default_true]
    schema_version: Mapped[_str8]

    if TYPE_CHECKING:
        finca: Mapped[FincaRow]
    else:
        finca = relationship("FincaRow", lazy="joined")


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
        schema_version: Per-row schema version, always copied from the
            domain record; this column declares no default of its own.
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

    id: Mapped[_intpk]
    contract_id: Mapped[_contract_fk]
    period_year: Mapped[_int_required]
    gross_rent_received: Mapped[_decimal_15_2]
    dias_alquilados: Mapped[_int_required]
    schema_version: Mapped[_str8]

    if TYPE_CHECKING:
        contract: Mapped[ArrendamientoRow]
    else:
        contract = relationship("ArrendamientoRow", lazy="joined")


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
        schema_version: Per-row schema version, always copied from the
            domain record; this column declares no default of its own.
    """

    __tablename__ = "rental_expenses"
    __table_args__ = (
        CheckConstraint(
            f"category IN {_enum_check(_RENTAL_EXPENSE_CATEGORY_VALUES)}",
            name="ck_rental_expenses_category",
        ),
    )

    id: Mapped[_intpk]
    finca_id: Mapped[_finca_fk]
    period_year: Mapped[_int_required]
    category: Mapped[_str48]
    amount: Mapped[_decimal_15_2]
    schema_version: Mapped[_str8]

    if TYPE_CHECKING:
        finca: Mapped[FincaRow]
    else:
        finca = relationship("FincaRow", lazy="joined")


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

    id: Mapped[_intpk]
    finca_id: Mapped[_finca_fk]
    period_year: Mapped[_int_required]
    dias_alquilados: Mapped[_int_required]
    basis_used: Mapped[_decimal_15_2]
    amortization_amount: Mapped[_decimal_15_2]
    cumulative_amortization_through_year: Mapped[_decimal_15_2]
    schema_version: Mapped[_str8]

    if TYPE_CHECKING:
        finca: Mapped[FincaRow]
    else:
        finca = relationship("FincaRow", lazy="joined")


metadata = Base.metadata
"""Alembic ``target_metadata`` for autogenerate."""
