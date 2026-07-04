"""Encrypted SQL repository for the transaction catalogue.

:class:`TransactionCatalogueRepository` is the only sanctioned read/write path
for the transaction catalogue. It stores **one encrypted secure-object row per
transaction** — keyed ``transaction:{bucket_id}:{transaction_id}`` inside the
``aeat.domain.transactions.bucket`` namespace at
:class:`~adapters.persistence.storage.SensitivityClass` ``FINANCIAL`` — so a
single-transaction mutation rewrites only that row instead of re-encrypting the
whole catalogue (the prior single-blob shape was O(n) write amplification per
ledger edit). Each row wraps its
:class:`~domain.transactions.Transaction` in an
:class:`~adapters.persistence.storage.Envelope` before serialisation; no
plaintext transaction row, JSON catalogue, or envelope file lands on disk.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`. It
lives in the persistence adapter (not in :mod:`domain.transactions`) because
its secure-object coupling is SQL/crypto-bound; the domain package owns only the
pure surface — the :class:`~domain.transactions.ImportSummary` record, the
:func:`~domain.transactions.transaction_object_key` /
:func:`transaction_index_object_key` key-derivation helpers, and the
:data:`~domain.transactions.TX_BUCKET_NAMESPACE` /
schema-version constants that name the persisted envelope contract. The
namespace/version constants are redeclared here as the persisted-envelope
contract; the strings are preserved to avoid orphaning stored envelopes.

Writes go through the
:class:`~adapters.persistence.storage.SecureObjectRepository` atomic
upsert+delete batch
(:meth:`~adapters.persistence.storage.SecureObjectRepository.apply_batch`)
so a multi-transaction mutation — and any sibling-catalogue co-writes
(bucket-event history, invoices) passed to ``save_with_secure_object_writes`` —
commit all-or-nothing, preserving the co-write atomicity the single-blob
``save`` had. The diff that decides which rows to write or delete is driven by a
decryption-free
:meth:`~adapters.persistence.storage.SecureObjectRepository.namespace_payload_hashes`
scan, so an unchanged transaction is never rewritten.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.classification import SensitivityClass
from ....core.config import load_settings
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.time import now, validate_utc_aware
from ....domain.transactions import (
    LedgerStorageError,
    StoredTransactionDriftError,
    Transaction,
    TransactionCatalogue,
    transaction_index_object_key,
    transaction_object_key,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import (
        SecureObjectDeletion,
        SecureObjectRepository,
        SecureObjectWrite,
    )

_log = get_logger(__name__)

# namespace / schema-version strings preserved across the relocation to avoid
# orphaning persisted envelopes; redeclared here as the persisted-envelope contract.
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


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ..storage import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id, load_settings())


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


def _decode_persisted_transaction_row(payload: bytes) -> dict[str, object] | None:
    """Return the parsed envelope dict for one persisted row, or ``None`` if not JSON.

    Centralises the single JSON decode of a stored row's plaintext bytes so
    the D6 timestamp guard and the authoritative :class:`Envelope` validation
    share one parse instead of each independently re-decoding the same bytes
    (a real O(n) cost at ledger scale: see the P95 scale benchmark in
    ``application/aggregation/tests/test_ledger_scale_benchmark.py``).
    """
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _validate_persisted_transaction_timestamps(decoded: dict[str, object]) -> None:
    """Reject a persisted per-transaction row missing the mandatory D6 timestamps.

    Takes the already-JSON-decoded envelope dict (see
    :func:`_decode_persisted_transaction_row`) rather than re-parsing the raw
    bytes, so this guard adds only a cheap pydantic pass over the small
    ``{created_at, modified_at}`` sub-shape -- not a second full JSON decode
    of the whole row.
    """
    transaction_payload = decoded.get("payload")
    if not isinstance(transaction_payload, dict):
        return
    _PersistedTransactionTimestampWitness.validate_payload(transaction_payload)


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue.

    Every instance is bound to one profile bucket via ``bucket_id``. The
    catalogue is stored as one secure-object row per transaction (keyed
    ``transaction:{bucket_id}:{transaction_id}``) inside the
    :data:`adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`
    namespace, so two operator profiles never share transaction storage and a
    single-transaction mutation touches a single row. Each
    :class:`~domain.transactions.Transaction` payload and the bucket
    membership index are wrapped in
    :class:`~adapters.persistence.storage.Envelope` before
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    persists them. The class exposes the concrete load/save implementation
    behind
    :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to ``bucket_id``, resolving the bucket store when ``objects`` is omitted."""
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
            :class:`~adapters.persistence.storage.ClassificationError`:
                If a row's inner envelope class is not
                ``SensitivityClass.FINANCIAL``.
            :class:`~adapters.persistence.storage.EnvelopeVersionError`:
                If a row's inner envelope schema version is higher than the
                consumer supports.
            StoredTransactionDriftError: If a row payload fails pydantic schema
                validation on deserialization.
        """
        from ..storage import ClassificationError, Envelope, EnvelopeVersionError
        from ..storage.crypto import secure_object_key_digest

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
                decoded_row = _decode_persisted_transaction_row(record.payload)
                if decoded_row is not None:
                    # Reuse the same JSON decode for the cheap D6 timestamp
                    # guard; the authoritative Envelope validation below still
                    # parses the original bytes via ``model_validate_json``
                    # (JSON mode), which is required for correct string ->
                    # datetime / string -> enum coercion under the envelope's
                    # ``strict=True`` config -- ``model_validate`` on an
                    # already-decoded dict runs in *python* mode and rejects
                    # those coercions outright under strict config.
                    _validate_persisted_transaction_timestamps(decoded_row)
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
        decryption-free
        :meth:`~adapters.persistence.storage.SecureObjectRepository.namespace_payload_hashes`
        lookup keyed by the bucket-qualified HMAC digest (so it is correct even
        when several buckets share one store): an incoming transaction whose
        freshly-serialised payload hash matches the stored one is left
        untouched. Deletions and the membership index are bounded to *this*
        bucket via the per-bucket index, so a reconciliation can never touch
        another bucket's rows.
        """
        from ..storage import SecureObjectDeletion, SecureObjectWrite
        from ..storage.crypto import secure_object_key_digest

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
        from ..storage import Envelope

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
        from ..storage import Envelope

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
        from ..storage import Envelope

        envelope = Envelope[Transaction](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=transaction.modified_at,
            classification=SensitivityClass.FINANCIAL,
            payload=transaction,
        )
        return envelope.model_dump_json().encode("utf-8")


__all__ = [
    "TransactionCatalogueRepository",
]
