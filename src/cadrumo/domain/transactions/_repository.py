"""Domain-side transaction-catalogue port surface.

This module owns the pure transaction-catalogue persistence vocabulary that
carries no SQL/crypto coupling: the :class:`ImportSummary` record returned by a
ledger import and the :func:`transaction_object_key` /
:func:`transaction_index_object_key` secure-object key-derivation helpers. The
namespace and schema-version metadata are owned solely by the registry
authority :data:`adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`;
this domain port never redeclares them. The concrete encrypted SQL repository
lives in the persistence adapter
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`,
behind the read-side
:class:`~cadrumo.domain.transactions.TransactionCatalogueRepositoryProtocol`; the
domain package depends only on the structural port.

The namespace authority is
:data:`adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`; this module
derives the bucket-local transaction row keys with :func:`transaction_object_key`
and the membership-index key with :func:`transaction_index_object_key`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from .errors import LedgerStorageError
from ._models import BucketTransactionRef

#: Registered locale key for every key-derivation refusal in this module.
#: Read from the class's own bound :class:`~core.errors.ErrorCode` rather than
#: restated as a literal, so the raise sites and the error registry cannot
#: drift apart. The refusals below carry this key plus locale-neutral facts and
#: author no sentence: ``str(exc)`` prefers a positional argument over the key,
#: so an authored sentence passed alongside it would keep reaching tracebacks,
#: logs and every direct rendering in every locale.
_LEDGER_STORAGE_MESSAGE_KEY = LedgerStorageError.code.message_key


def transaction_index_object_key(bucket_id: str) -> str:
    """Return the per-bucket transaction-membership-index secure-object key.

    The index row shares
    :data:`adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`
    with the per-transaction rows and bounds reads/deletions to one bucket.
    """
    trimmed = bucket_id.strip()
    if not trimmed:
        raise LedgerStorageError(
            translated_message=_LEDGER_STORAGE_MESSAGE_KEY,
            context={
                "repository": "transaction_catalogue",
                "operation": "index_object_key",
                "blank_field": "bucket_id",
            },
        )
    return f"transaction-index:{trimmed}"


def transaction_object_key(bucket_id: str, transaction_id: str) -> str:
    """Return the per-transaction secure-object key within a profile bucket.

    Each transaction is its own secure-object row. The key qualifies with the
    bucket id (``transaction:{bucket_id}:{transaction_id}``); cross-bucket
    aggregation must qualify with ``(bucket_id, tx_id)`` because ``tx_id`` alone
    is unique only within one bucket. Rows live under
    :data:`adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`.
    """
    trimmed = bucket_id.strip()
    if not trimmed:
        raise LedgerStorageError(
            translated_message=_LEDGER_STORAGE_MESSAGE_KEY,
            context={
                "repository": "transaction_catalogue",
                "operation": "object_key",
                "blank_field": "bucket_id",
            },
        )
    tx = transaction_id.strip()
    if not tx:
        raise LedgerStorageError(
            translated_message=_LEDGER_STORAGE_MESSAGE_KEY,
            context={
                "repository": "transaction_catalogue",
                "operation": "object_key",
                "blank_field": "transaction_id",
            },
        )
    return f"transaction:{trimmed}:{tx}"


class ImportSummary(BaseModel):
    """Frozen summary of one ledger import persistence operation.

    Attributes:
        imported: Number of new transactions persisted by this call.
        skipped: Number of input rows already present in the catalogue.
            A row is a duplicate when its stable import fingerprint
            (:func:`derive_import_fingerprint`) is already present —
            the fingerprint is stamped at import and survives both
            later edits and a re-export in a different file format.
        errors: Reserved for future per-row error counts; today the
            repository raises on any error rather than tallying.
        likely_duplicate_refs: Rows that were imported but share an
            effective date and amount with an existing transaction
            while carrying a divergent narrative — a probable, but
            not confident, cross-format duplicate. The operator is
            warned so they can review rather than discovering a silent
            double-count later.
        catalogue_path: Logical URI of the encrypted database object.
    """

    model_config = STRICT_FROZEN_CONFIG

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    bucket_id: BucketId
    imported_refs: tuple[BucketTransactionRef, ...] = ()
    skipped_refs: tuple[BucketTransactionRef, ...] = ()
    likely_duplicate_refs: tuple[BucketTransactionRef, ...] = ()
    catalogue_path: str


__all__ = [
    "ImportSummary",
    "transaction_index_object_key",
    "transaction_object_key",
]
