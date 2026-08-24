"""Encrypted persistence for the transaction-to-revision participation index.

The participation index is a derived, rebuildable read-side cache linking one
ledger transaction id to the finalized modelo revisions, filings, and
justificantes that consumed it. This concrete repository is the persistence
adapter behind the pure :mod:`~domain.modelos` index model: it stores one
:class:`~adapters.persistence.storage.Envelope` per transaction at
:class:`~adapters.persistence.storage.SensitivityClass` FINANCIAL under the
active profile bucket, mirroring the :class:`~domain.modelos.CalculationRevision`
catalogue repository.

Living in the persistence adapter (not in :mod:`~domain.modelos`) keeps the
:class:`~adapters.persistence.storage.SecureObjectRepository` /
:class:`~adapters.persistence.storage.Envelope` coupling out of the domain
layer; the domain package owns only the typed index model, its derivation, and
the object-key grammar. The index is critically sensitive financial data; no
plaintext index is ever written to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core import resolve_repository_bucket_id
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.modelos import (
    TransactionParticipationIndexPersistenceError,
    TransactionRevisionParticipationIndex,
    derive_participation_index_id,
)
from ..storage import TRANSACTION_PARTICIPATION_INDEX_NAMESPACE, secure_object_repository_for_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from collections.abc import Iterable

    from ..storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)

# Namespace, sensitivity, and schema version are sourced from the single registry
# authority, which is their sole declaration site.
_PARTICIPATION_INDEX_NAMESPACE = TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.namespace
_PARTICIPATION_INDEX_SENSITIVITY = TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.sensitivity
_PARTICIPATION_INDEX_SCHEMA_VERSION = TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.schema_version

# Locale key for participation-index persistence failures (mirrors the message
# the domain calculation-revision persistence path uses).
_PARTICIPATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"


class TransactionParticipationIndexRepository:
    """Read / write one transaction's participation index in encrypted storage.

    Mirrors the :class:`~domain.modelos.CalculationRevision` catalogue
    repository: persistence is delegated to
    :class:`~adapters.persistence.storage.SecureObjectRepository` at
    :class:`~adapters.persistence.storage.SensitivityClass` FINANCIAL under
    the active profile bucket, one secure object per ``transaction_id``. The
    participation index is critically sensitive financial data (it links a
    ledger transaction to its filings); no plaintext index is ever written to
    disk.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to an explicit secure-object store or profile bucket."""
        if objects is not None:
            self._objects = objects
            self._bucket_id = bucket_id.strip() if bucket_id is not None else None
            return
        self._bucket_id = resolve_repository_bucket_id(
            bucket_id,
            error_type=TransactionParticipationIndexPersistenceError,
        )
        self._objects = secure_object_repository_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Identifier of the per-profile storage bucket this repository reads and writes."""
        return self._bucket_id

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the :class:`~adapters.persistence.storage.SecureObjectRepository` backend."""
        return self._objects

    def exists(self, transaction_id: str) -> bool:
        """Report whether a participation index has been persisted for ``transaction_id``."""
        return self._objects.exists(_PARTICIPATION_INDEX_NAMESPACE, derive_participation_index_id(transaction_id))

    def load(self, transaction_id: str) -> TransactionRevisionParticipationIndex:
        """Load and decrypt one transaction's persisted participation index.

        Returns an empty :class:`TransactionRevisionParticipationIndex` for that
        transaction when nothing has been persisted yet, rather than raising.

        The decrypted payload's own ``transaction_id`` must rebuild the key the
        row is filed under. It is the same fact twice --
        :meth:`to_secure_object_write` derives the key FROM the payload, so the
        write path cannot disagree with itself and needs no check; only a row
        that arrived some other way can. Without the comparison, an index
        belonging to transaction B read through A's key attributed B's
        finalized-revision participations to A, which is what the ledger
        deletion guard and the operator cross-reference both read.

        Raises:
            TransactionParticipationIndexPersistenceError: The stored row fails
                the classification or envelope-version gate.
            SecureObjectRowIdentityError: The payload names a different
                transaction than the key it is filed under. Raised as the
                substrate's own identity error rather than translated, so this
                condition is the one recognisable failure across every
                key-addressed repository instead of a per-repository dialect.
        """
        from ..storage import (
            ClassificationError,
            Envelope,
            EnvelopeVersionError,
            SecureObjectRowIdentityError,
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )
        from ..storage.crypto import secure_object_key_digest

        object_key = derive_participation_index_id(transaction_id)
        try:
            record = self._objects.load(
                _PARTICIPATION_INDEX_NAMESPACE,
                object_key,
                expected_class=_PARTICIPATION_INDEX_SENSITIVITY,
                max_supported_version=_PARTICIPATION_INDEX_SCHEMA_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("participation-index integrity error", exc_info=True)
            raise TransactionParticipationIndexPersistenceError(
                "participation-index integrity error",
                translated_message=_PARTICIPATION_PERSISTENCE_MESSAGE,
                context={"reason": "secure_object_integrity", "cause_type": type(exc).__name__},
            ) from exc
        if record is None:
            return TransactionRevisionParticipationIndex(transaction_id=object_key)
        envelope = Envelope[TransactionRevisionParticipationIndex].model_validate_json(
            record.payload.decode(UTF_8_ENCODING),
        )
        if not inner_envelope_classification_is_expected(envelope.classification, _PARTICIPATION_INDEX_SENSITIVITY):
            _LOGGER.error("participation-index classification mismatch")
            raise TransactionParticipationIndexPersistenceError(
                "participation-index classification mismatch",
                translated_message=_PARTICIPATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": _PARTICIPATION_INDEX_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _PARTICIPATION_INDEX_SCHEMA_VERSION):
            _LOGGER.error("participation-index envelope version unsupported")
            raise TransactionParticipationIndexPersistenceError(
                "participation-index envelope version unsupported",
                translated_message=_PARTICIPATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _PARTICIPATION_INDEX_SCHEMA_VERSION,
                },
            )
        payload = envelope.payload
        payload_key = derive_participation_index_id(payload.transaction_id)
        if secure_object_key_digest(payload_key) != record.object_key:
            _LOGGER.error("participation-index row identity mismatch")
            raise SecureObjectRowIdentityError(
                _PARTICIPATION_INDEX_NAMESPACE,
                expected_identifier=payload_key,
            )
        return payload

    def save(self, index: TransactionRevisionParticipationIndex) -> None:
        """Persist one transaction's participation index to encrypted storage."""
        self._objects.save_many((self.to_secure_object_write(index),))

    def replace_all(self, indexes: Iterable[TransactionRevisionParticipationIndex]) -> int:
        """Atomically make ``indexes`` the complete persisted participation index.

        The participation index is a derived cache whose authority is the
        calculation-revision catalogue, so a regeneration must be a *replace*,
        not an upsert: a transaction whose last finalized revision was discarded
        or removed has no entry in the regenerated set, and its stale secure
        object must disappear with it. Upserting only the regenerated rows would
        leave that object readable through
        :meth:`load` / :meth:`exists`, letting the derived cache surface
        participations the authoritative catalogue no longer records.

        Every upsert and every stale-row removal commits in one
        :meth:`~adapters.persistence.storage.SecureObjectRepository.apply_batch`
        unit of work, so a crash mid-replace rolls back to the previous complete
        index rather than a half-pruned one.

        Stale rows are addressed by their stored HMAC digest: natural object keys
        are unrecoverable from the index (see
        :meth:`~adapters.persistence.storage.SecureObjectRepository.list_keys`),
        so the retained set is digested with the same
        ``secure_object_key_digest`` the storage column binds with and the
        difference is deleted by digest. This keeps the prune decryption-free.

        Returns:
            The number of stale participation objects removed.
        """
        from ..storage import SecureObjectDeletion
        from ..storage.crypto import secure_object_key_digest

        writes = tuple(self.to_secure_object_write(index) for index in indexes)
        retained = {secure_object_key_digest(write.object_key).hex() for write in writes}
        deletions = tuple(
            SecureObjectDeletion(
                namespace=_PARTICIPATION_INDEX_NAMESPACE,
                hashed_object_key=bytes.fromhex(stored_key),
            )
            for stored_key in self._objects.list_keys(_PARTICIPATION_INDEX_NAMESPACE)
            if stored_key not in retained
        )
        self._objects.apply_batch(writes, deletions)
        return len(deletions)

    def to_secure_object_write(self, index: TransactionRevisionParticipationIndex) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` upsert for ``index`` without committing it.

        Mirrors the bucket-event-history repository so the participation write
        can be passed to ``save_with_secure_object_writes`` as an extra write
        slot, co-emitting atomically with the revision save.
        """
        from ..storage import Envelope, SecureObjectWrite

        envelope = Envelope[TransactionRevisionParticipationIndex](
            schema_version=_PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=now(),
            classification=_PARTICIPATION_INDEX_SENSITIVITY,
            payload=index,
        )
        return SecureObjectWrite(
            namespace=_PARTICIPATION_INDEX_NAMESPACE,
            object_key=derive_participation_index_id(index.transaction_id),
            classification=_PARTICIPATION_INDEX_SENSITIVITY,
            schema_version=_PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )


__all__ = [
    "TransactionParticipationIndexRepository",
]
