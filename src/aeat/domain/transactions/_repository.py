"""Governed-persistence repository for the transaction catalogue.

The repository is the only sanctioned read/write path for the transaction
catalogue. It stores **one encrypted secure-object row per transaction** —
keyed ``transaction:{bucket_id}:{transaction_id}`` inside the
``aeat.domain.transactions.bucket`` namespace at :class:`SensitivityClass`
``FINANCIAL`` — so a single-transaction mutation rewrites only that row instead
of re-encrypting the whole catalogue (the prior single-blob shape was O(n) write
amplification per ledger edit). Each row wraps its :class:`Transaction` in an
:class:`Envelope` before serialisation; no plaintext transaction row, JSON
catalogue, or envelope file lands on disk.

Writes go through the :class:`SecureObjectRepository` atomic upsert+delete batch
(:meth:`SecureObjectRepository.apply_batch`) so a multi-transaction mutation —
and any sibling-catalogue co-writes (bucket-event history, invoices) passed to
:meth:`save_with_secure_object_writes` — commit all-or-nothing, preserving the
co-write atomicity the single-blob ``save`` had. The diff that decides which
rows to write or delete is driven by a decryption-free
:meth:`SecureObjectRepository.namespace_payload_hashes` scan, so an unchanged
transaction is never rewritten.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError, field_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.classification import SensitivityClass
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...core.time import now, validate_utc_aware
from ._errors import LedgerStorageError, StoredTransactionDriftError
from ._models import BucketTransactionRef, Transaction, TransactionCatalogue

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import (
        SecureObjectDeletion,
        SecureObjectRepository,
        SecureObjectWrite,
    )

_log = get_logger(__name__)

_TX_CATALOGUE_VERSION = 1
TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket"


class _TransactionIndex(BaseModel):
    """Per-bucket membership list: the transaction ids this bucket owns.

    The index is a single secure-object row keyed by ``bucket_id`` that bounds
    both reads and deletions to *this* bucket's rows. It is what preserves
    cross-bucket isolation when several buckets share one secure store: a load
    or a reconciliation reads this bucket's index by its exact key and never
    enumerates another bucket's transactions, and a reconciliation can only
    delete transaction ids the index lists. The heavy per-transaction payloads
    live in their own rows; the index carries only the (cheap) id list.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_ids: tuple[str, ...] = ()


def transaction_index_object_key(bucket_id: str) -> str:
    """Return the per-bucket transaction-membership-index secure-object key."""
    trimmed = bucket_id.strip()
    if not trimmed:
        raise LedgerStorageError(
            "bucket_id must not be blank",
            context={"repository": "transaction_catalogue", "operation": "index_object_key"},
        )
    return f"transaction-index:{trimmed}"


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ...adapters.persistence.storage import secure_object_repository_for_bucket
    from ...core.config import load_settings

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def transaction_object_key(bucket_id: str, transaction_id: str) -> str:
    """Return the per-transaction secure-object key within a profile bucket.

    Each transaction is its own secure-object row. The key qualifies with the
    bucket id (``transaction:{bucket_id}:{transaction_id}``); cross-bucket
    aggregation must qualify with ``(bucket_id, tx_id)`` because ``tx_id`` alone
    is unique only within one bucket.
    """
    trimmed = bucket_id.strip()
    if not trimmed:
        raise LedgerStorageError(
            "bucket_id must not be blank",
            context={"repository": "transaction_catalogue", "operation": "object_key"},
        )
    tx = transaction_id.strip()
    if not tx:
        raise LedgerStorageError(
            "transaction_id must not be blank",
            context={"repository": "transaction_catalogue", "operation": "object_key"},
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


class _PersistedTransactionTimestampWitness(BaseModel):
    """Required lifecycle timestamps for one stored transaction row."""

    created_at: datetime = Field()
    modified_at: datetime = Field()

    @field_validator("created_at", "modified_at")
    @classmethod
    def _require_utc_aware(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def validate_payload(cls, payload: object) -> None:
        """Raise ``ValidationError`` when a persisted row lacks timestamp keys."""
        cls.model_validate(payload)


def _validate_persisted_transaction_timestamps(payload: bytes) -> None:
    """Reject a persisted per-transaction row missing the mandatory D6 timestamps."""
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(decoded, dict):
        return
    transaction_payload = decoded.get("payload")
    if not isinstance(transaction_payload, dict):
        return
    _PersistedTransactionTimestampWitness.validate_payload(transaction_payload)


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue.

    Every instance is bound to one profile bucket via ``bucket_id``. The
    catalogue is stored as one secure-object row per transaction (keyed
    ``transaction:{bucket_id}:{transaction_id}``) inside the
    ``aeat.domain.transactions.bucket`` namespace, so two operator profiles
    never share transaction storage and a single-transaction mutation touches a
    single row.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LedgerStorageError(
                "bucket_id must not be blank",
                context={"repository": "transaction_catalogue", "operation": "object_key"},
            )
        self._objects = objects or _secure_objects_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket id this repository is bound to."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether this bucket holds any persisted transactions."""
        return bool(self._load_index_ids())

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue, assembled from this bucket's rows.

        The per-bucket membership index names exactly the transaction ids this
        bucket owns; only the rows whose digest the index lists are read, so a
        shared secure store never leaks another bucket's transactions.

        Returns:
            The deserialised :class:`TransactionCatalogue`, or a fresh empty
            instance when this bucket has no transactions.

        Raises:
            ClassificationError: If a row's inner envelope class is not
                ``SensitivityClass.FINANCIAL``.
            EnvelopeVersionError: If a row's inner envelope schema version is
                higher than the consumer supports.
            StoredTransactionDriftError: If a row payload fails pydantic schema
                validation on deserialization.
        """
        from ...adapters.persistence.storage import Envelope
        from ...adapters.persistence.storage.crypto import secure_object_key_digest
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        index_ids = self._load_index_ids()
        if not index_ids:
            return TransactionCatalogue.from_transactions([])
        wanted = {
            secure_object_key_digest(transaction_object_key(self._bucket_id, transaction_id)): transaction_id
            for transaction_id in index_ids
        }
        transactions: list[Transaction] = []
        for record in self._objects.list_records(
            TX_BUCKET_NAMESPACE,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        ):
            transaction_id = wanted.get(bytes(record.object_key))
            if transaction_id is None:
                continue  # the index row, or (shared store) another bucket's row
            try:
                _validate_persisted_transaction_timestamps(record.payload)
                envelope = Envelope[Transaction].model_validate_json(record.payload)
            except ValidationError as exc:
                _log.error(
                    "transaction row schema drift bucket_id=%s",
                    self._bucket_id,
                    exc_info=True,
                )
                raise StoredTransactionDriftError(self._bucket_id, exc) from exc
            if envelope.classification is not SensitivityClass.FINANCIAL:
                raise ClassificationError(
                    context={
                        "namespace": TX_BUCKET_NAMESPACE,
                        "object_key": transaction_object_key(self._bucket_id, transaction_id),
                        "bucket_id": self._bucket_id,
                        "classification": envelope.classification.value,
                        "expected": SensitivityClass.FINANCIAL.value,
                    },
                    translated_message="errors.integrity.integrity_storage_classification",
                )
            if envelope.schema_version > _TX_CATALOGUE_VERSION:
                raise EnvelopeVersionError(
                    context={
                        "namespace": TX_BUCKET_NAMESPACE,
                        "object_key": transaction_object_key(self._bucket_id, transaction_id),
                        "bucket_id": self._bucket_id,
                        "schema_version": envelope.schema_version,
                        "expected": _TX_CATALOGUE_VERSION,
                    },
                    translated_message="errors.integrity.integrity_storage_envelope_version",
                )
            transactions.append(envelope.payload)
        _log.debug(
            "loaded transaction catalogue bucket_id=%s entries=%d",
            self._bucket_id,
            len(transactions),
        )
        return TransactionCatalogue.from_transactions(transactions)

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` as per-transaction encrypted rows.

        Only rows whose content changed are rewritten; transactions removed from
        the catalogue are deleted. The whole diff commits atomically.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
        """
        writes, deletions = self._reconcile(catalogue)
        self._objects.apply_batch(writes, deletions)
        _log.info(
            "saved transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
        )

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        The per-transaction diff (changed rows + deletions) and ``extra_writes``
        (e.g. bucket-event history, invoice catalogue) commit atomically, so a
        ledger mutation and its co-emitted records remain all-or-nothing.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
            extra_writes: Additional secure object writes to commit atomically.
        """
        writes, deletions = self._reconcile(catalogue)
        self._objects.apply_batch((*writes, *extra_writes), deletions)
        _log.info(
            "saved transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d extra_writes=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
            len(extra_writes),
        )

    def _reconcile(
        self,
        catalogue: TransactionCatalogue,
    ) -> tuple[tuple[SecureObjectWrite, ...], tuple[SecureObjectDeletion, ...]]:
        """Diff ``catalogue`` against this bucket's stored rows.

        Returns ``(changed writes, deletions)``. Changed-row detection is a
        decryption-free :meth:`namespace_payload_hashes` lookup keyed by the
        bucket-qualified HMAC digest (so it is correct even when several buckets
        share one store): an incoming transaction whose freshly-serialised
        payload hash matches the stored one is left untouched. Deletions and the
        membership index are bounded to *this* bucket via the per-bucket index,
        so a reconciliation can never touch another bucket's rows.
        """
        from ...adapters.persistence.storage import SecureObjectDeletion, SecureObjectWrite
        from ...adapters.persistence.storage.crypto import secure_object_key_digest
        from ...core.hashing import sha256_hex

        current_ids = self._load_index_ids()
        incoming_ids = set(catalogue.transactions)
        stored_hashes = self._objects.namespace_payload_hashes(TX_BUCKET_NAMESPACE)

        writes: list[SecureObjectWrite] = []
        for transaction_id, transaction in catalogue.transactions.items():
            object_key = transaction_object_key(self._bucket_id, transaction_id)
            digest = secure_object_key_digest(object_key)
            payload = self._serialise_transaction(transaction)
            if stored_hashes.get(digest) == sha256_hex(payload):
                continue
            writes.append(
                SecureObjectWrite(
                    namespace=TX_BUCKET_NAMESPACE,
                    object_key=object_key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=_TX_CATALOGUE_VERSION,
                    written_at=transaction.modified_at,
                    payload=payload,
                ),
            )

        if incoming_ids != current_ids:
            writes.append(
                SecureObjectWrite(
                    namespace=TX_BUCKET_NAMESPACE,
                    object_key=transaction_index_object_key(self._bucket_id),
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=_TX_CATALOGUE_VERSION,
                    written_at=now(),
                    payload=self._serialise_index(incoming_ids),
                ),
            )

        deletions = tuple(
            SecureObjectDeletion(
                namespace=TX_BUCKET_NAMESPACE,
                hashed_object_key=secure_object_key_digest(transaction_object_key(self._bucket_id, transaction_id)),
            )
            for transaction_id in current_ids - incoming_ids
        )
        return tuple(writes), deletions

    def _load_index_ids(self) -> set[str]:
        """Return the transaction ids the per-bucket membership index records."""
        from ...adapters.persistence.storage import Envelope

        record = self._objects.load(
            TX_BUCKET_NAMESPACE,
            transaction_index_object_key(self._bucket_id),
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        if record is None:
            return set()
        try:
            envelope = Envelope[_TransactionIndex].model_validate_json(record.payload)
        except ValidationError as exc:
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        return set(envelope.payload.transaction_ids)

    def _serialise_index(self, transaction_ids: set[str]) -> bytes:
        """Serialise the membership index (sorted ids) into encrypted-row bytes."""
        from ...adapters.persistence.storage import Envelope

        envelope = Envelope[_TransactionIndex](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=_TransactionIndex(transaction_ids=tuple(sorted(transaction_ids))),
        )
        return envelope.model_dump_json().encode("utf-8")

    def _serialise_transaction(self, transaction: Transaction) -> bytes:
        """Serialise one transaction into stable encrypted-row envelope bytes.

        The envelope ``written_at`` is the transaction's own ``modified_at`` (not
        ``now()``), so an unchanged transaction serialises to identical bytes —
        and an identical ``payload_hash`` — letting the diff skip rewriting it.
        """
        from ...adapters.persistence.storage import Envelope

        envelope = Envelope[Transaction](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=transaction.modified_at,
            classification=SensitivityClass.FINANCIAL,
            payload=transaction,
        )
        return envelope.model_dump_json().encode("utf-8")


__all__ = [
    "TX_BUCKET_NAMESPACE",
    "ImportSummary",
    "TransactionCatalogueRepository",
    "transaction_object_key",
]
