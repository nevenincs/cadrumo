"""SQLAlchemy Core table declarations for the primary storage database.

Declares the schema materialised by the storage engine. Intentionally kept
out of the :mod:`adapters.persistence.storage` public API: repositories
bridge between these rows and their typed records. The tables are plain Core
:class:`~sqlalchemy.Table` objects because no repository maps rows onto
objects; every read and write is an explicit statement over a connection.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from ..crypto.encrypted_columns import HashedLookup

_HASH_HEX_LENGTH = 64


def _nullable_fixed_length_check(column_name: str, expected_length: int) -> CheckConstraint:
    return CheckConstraint(
        f"{column_name} IS NULL OR length({column_name}) = {expected_length}",
        name=f"ck_secure_objects_{column_name}_len",
    )


metadata = MetaData()
"""Every table the storage engine materialises on first access."""

transaction_date_index_table = Table(
    "transaction_date_index",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bucket_id", String(64), nullable=False),
    Column("transaction_id", String(64), nullable=False),
    Column("filing_date", Date(), nullable=False),
    Column("filing_year", Integer, nullable=False),
    Column("eligible_from", Date(), nullable=False),
    Column("eligible_to", Date(), nullable=False),
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
"""Plaintext routing rows: one ledger transaction's filing date and year.

This table is a derived, rebuildable read-side cache co-written atomically
with ``secure_objects`` ledger writes (see
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`).
It exists purely to let a period-scoped ledger read select the candidate
transaction ids for a date range with a plaintext SQL predicate, so only
those rows need to be decrypted -- never the whole per-bucket catalogue.

A row carries ONLY non-sensitive routing keys: the bucket id, the
transaction id, its filing date (``value_date`` or ``booked_date`` -- the
same field every ledger aggregator already filters on), the filing year the
date falls in, and the inclusive span of every date the row can file an
observation under. No amount, counterparty, description, NIF, or other
financial content may ever be added to this table; it is plaintext by design
(:class:`~core.classification.policies.SensitivityClass` ``CACHE``) and
correctness never depends on it being present or fresh -- a missing or
incomplete index falls back to the full encrypted scan.

Columns:
    id: Surrogate integer primary key.
    bucket_id: Owning profile bucket, so a shared database never mixes two
        buckets' routing rows.
    transaction_id: The ledger transaction's stable content-derived id.
    filing_date: ``value_date`` or ``booked_date`` (whichever the ledger
        aggregation layer would use) as a plain SQL ``Date``.
    filing_year: ``filing_date.year``, indexed separately so a year-scoped
        candidate-id query does not need a date-range predicate at all.
    eligible_from: Earliest date this row can file an observation under, per
        :func:`~domain.transactions.dates.transaction_eligible_date_span`.
        Equal to ``filing_date`` unless an IVA criterio-de-caja timing
        override moves the row's devengo or collection dates off it.
    eligible_to: Latest such date, inclusive. A period-scoped partition
        selects on span OVERLAP rather than on ``filing_date``, so a row
        booked in one quarter that carries a prior-quarter cash-accounting
        devengo is never dropped from the candidate set.
"""

secure_objects_table = Table(
    "secure_objects",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("namespace", String(128), nullable=False),
    Column("object_key", HashedLookup(), nullable=False),
    Column("classification", String(32), nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("written_at", DateTime(timezone=True), nullable=False),
    Column("revision_id", String(64), nullable=True),
    Column("previous_revision_id", String(64), nullable=True),
    Column("revision_ancestor_ids", Text, nullable=True),
    Column("previous_payload_hash", String(64), nullable=True),
    Column("payload_hash", String(64), nullable=True),
    Column("ciphertext_hash", String(64), nullable=True),
    Column("revision_written_at", DateTime(timezone=True), nullable=True),
    Column("write_provenance", String(255), nullable=True),
    Column("source_event_id", String(128), nullable=True),
    Column("conflict_policy", String(32), nullable=True),
    Column("payload", LargeBinary, nullable=False),
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
"""Encrypted byte-object rows for sensitive application payloads.

Domain repositories use this table for financial catalogues and workflow
state that must not land as standalone JSON files. The ``payload`` column is
a SQL BLOB holding the AEAD wire bytes; the repository encrypts and decrypts
it explicitly (rather than through a column ``TypeDecorator``) so the row
identity (``namespace`` + ``object_key`` digest + ``schema_version``) can be
bound into the AEAD associated data, making a ciphertext refuse to decrypt
under any other row. The remaining columns are routing, revision-lineage,
and integrity metadata.
"""
