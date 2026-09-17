"""Internal SQLAlchemy ORM mapper classes.

Declares the schema materialised by the storage engine. Intentionally kept
out of the :mod:`adapters.persistence.storage` public API: repositories
bridge between these rows and their typed records.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..crypto.encrypted_columns import HashedLookup

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

_str32 = Annotated[str, mapped_column(String(32), nullable=False)]
_str32_opt = Annotated[str | None, mapped_column(String(32), nullable=True)]
_str64 = Annotated[str, mapped_column(String(64), nullable=False)]
_str64_opt = Annotated[str | None, mapped_column(String(64), nullable=True)]
_str128 = Annotated[str, mapped_column(String(128), nullable=False)]
_str128_opt = Annotated[str | None, mapped_column(String(128), nullable=True)]
_str255_opt = Annotated[str | None, mapped_column(String(255), nullable=True)]
_text_opt = Annotated[str | None, mapped_column(Text, nullable=True)]

_int_required = Annotated[int, mapped_column(Integer, nullable=False)]

_date_required = Annotated[date, mapped_column(Date(), nullable=False)]
_datetime_tz = Annotated[datetime, mapped_column(DateTime(timezone=True), nullable=False)]
_datetime_tz_opt = Annotated[datetime | None, mapped_column(DateTime(timezone=True), nullable=True)]

_large_binary = Annotated[bytes, mapped_column(LargeBinary, nullable=False)]
_hashed_lookup = Annotated[bytes, mapped_column(HashedLookup(), nullable=False)]


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
    plaintext by design (:class:`~core.classification.policies.SensitivityClass`
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
            per :func:`~domain.transactions.dates.transaction_eligible_date_span`.
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


metadata = Base.metadata
"""Alembic ``target_metadata`` for autogenerate."""
