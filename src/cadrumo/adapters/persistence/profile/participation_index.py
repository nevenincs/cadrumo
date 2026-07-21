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

from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.modelos import (
    TransactionParticipationIndexPersistenceError,
    TransactionRevisionParticipationIndex,
    derive_participation_index_id,
)
from ..storage import TRANSACTION_PARTICIPATION_INDEX_NAMESPACE
from ._modelo_runtime import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)

# Namespace, sensitivity, and schema version are sourced from the single registry
# authority. The registry def's value mirrors the domain-owned
# ``PARTICIPATION_INDEX_NAMESPACE`` string; the adapter consumes the def.
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
        self._bucket_id = resolve_modelo_repository_bucket_id(
            bucket_id,
            error_type=TransactionParticipationIndexPersistenceError,
        )
        self._objects = secure_objects_for_modelo_bucket(self._bucket_id)

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
        """
        from ..storage import ClassificationError, Envelope, EnvelopeVersionError

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
        if envelope.classification is not _PARTICIPATION_INDEX_SENSITIVITY:
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
        if envelope.schema_version > _PARTICIPATION_INDEX_SCHEMA_VERSION:
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
        return envelope.payload

    def save(self, index: TransactionRevisionParticipationIndex) -> None:
        """Persist one transaction's participation index to encrypted storage."""
        self._objects.save_many((self.to_secure_object_write(index),))

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
