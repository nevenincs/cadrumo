"""Transaction-to-revision participation index for audit cross-reference.

The ledger persists only the forward link: a :class:`CalculationRevision`
names its ``source_transaction_ids``. The inverse question an auditor asks of a
single ledger transaction — which finalized modelo revisions, filings, and
justificantes consumed it — has no persisted, surfaced answer; the only inverse
traversal is the transient ``_blocking_modelo_references`` write-guard scan.

This module introduces the :class:`TransactionRevisionParticipationIndex`, a
derived, rebuildable secure-object recording, per ledger transaction id, the set
of finalized-revision participations: the ``calculation_revision_id``,
``work_unit_id``, ``modelo``, ``filing_year``, ``period`` and ``revision_state``,
plus, where the revision is filed, the ``filing_record_id`` and the
justificante reference. The index is co-written atomically inside the same
``save_with_secure_object_writes`` unit of work that persists the revision (per
the composition-service single-writer discipline); it is a read-side cache, never
a second source of truth, and is fully rebuildable from the revision catalogue.

The index is keyed by ``transaction_id`` and persisted one secure :class:`Envelope` per
transaction, so a revision over N contributing transactions co-emits N index
upserts. Each upsert merges its new participation into that transaction's entry
without disturbing the participations already recorded for it.

See :func:`derive_participation_index_id` for the object-key grammar, and the
``TransactionParticipationIndexRepository`` for the encrypted persistence
boundary mirroring the :class:`CalculationRevision` catalogue repository at
:class:`SensitivityClass` FINANCIAL.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ...core import Period
from ...core.identity import TransactionId
from ...core.logging import get_logger
from ...core.time import now
from ._codes import ModeloCode
from ._errors import ModeloError, ModeloValidationError
from ._ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)

PARTICIPATION_INDEX_NAMESPACE = "aeat.domain.modelos.participation_index"
PARTICIPATION_INDEX_SCHEMA_VERSION = 1
_PARTICIPATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"

_JustificanteReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_RevisionState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]


def derive_participation_index_id(transaction_id: str) -> str:
    """Return the secure-object key for one transaction's participation entry.

    The index is content-addressed by the ledger transaction id: each
    :class:`TransactionId` owns exactly one
    :class:`TransactionRevisionParticipationIndex` secure object, so the object
    key IS the (trimmed) transaction id. This keeps the inverse lookup an O(1)
    keyed read from a transaction id alone.
    """
    trimmed = transaction_id.strip()
    if not trimmed:
        raise ModeloValidationError("participation-index transaction_id must not be blank")
    return trimmed


class TransactionRevisionParticipation(BaseModel):
    """One finalized-revision participation recorded against a ledger transaction.

    Records that a single ledger transaction contributed to one finalized
    :class:`CalculationRevision`. ``filing_record_id`` and
    ``justificante_reference`` are populated only when the revision reached a
    filed state; a freshly verified-complete (not yet filed) participation
    leaves both ``None``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: Period
    revision_state: _RevisionState
    filing_record_id: FilingRecordId | None = None
    justificante_reference: _JustificanteReference | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_modelo(cls, data: object) -> object:
        if isinstance(data, Mapping) and "modelo" in data:
            value = data["modelo"]
            if isinstance(value, str) and not isinstance(value, ModeloCode):
                mutable = dict(data)
                mutable["modelo"] = ModeloCode(value)
                return mutable
        return data

    @model_validator(mode="after")
    def _enforce_period_year(self) -> TransactionRevisionParticipation:
        if self.period.filing_year != self.filing_year:
            raise ModeloValidationError(
                f"filing_year {self.filing_year!r} does not match period year {self.period.filing_year!r}",
            )
        return self


class TransactionRevisionParticipationIndex(BaseModel):
    """All finalized-revision participations recorded for one ledger transaction.

    Keyed-by-transaction secure object: each instance carries the full,
    ordered participation set for a single :class:`TransactionId`. The
    ``model_validator`` rejects duplicate ``calculation_revision_id`` entries so
    a re-emission cannot accumulate a second row for the same revision; an
    upsert (:func:`upsert_transaction_participation`) replaces in place instead.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    transaction_id: TransactionId
    participations: tuple[TransactionRevisionParticipation, ...] = ()

    @model_validator(mode="after")
    def _reject_duplicate_revisions(self) -> TransactionRevisionParticipationIndex:
        seen = [item.calculation_revision_id for item in self.participations]
        if len(seen) != len(set(seen)):
            raise ModeloValidationError(
                "participation index carries duplicate calculation_revision_id entries for one transaction",
            )
        return self


def upsert_transaction_participation(
    index: TransactionRevisionParticipationIndex,
    participation: TransactionRevisionParticipation,
) -> TransactionRevisionParticipationIndex:
    """Return a new index with ``participation`` merged into the transaction's entry.

    The merge is keyed by ``calculation_revision_id``: an existing entry for the
    same revision is REPLACED in place (so a verified-then-filed transition
    overwrites the verified row with the filed one, gaining
    ``filing_record_id``), and a new revision is APPENDED. Participations for
    other revisions are never disturbed, and entry order is otherwise stable so
    the audit trail reads chronologically.
    """
    replaced = False
    merged: list[TransactionRevisionParticipation] = []
    for existing in index.participations:
        if existing.calculation_revision_id == participation.calculation_revision_id:
            merged.append(participation)
            replaced = True
        else:
            merged.append(existing)
    if not replaced:
        merged.append(participation)
    return index.model_copy(update={"participations": tuple(merged)})


class TransactionParticipationIndexPersistenceError(ModeloError):
    """Raised when the participation index cannot be persisted or loaded."""


class TransactionParticipationIndexRepository:
    """Read / write one transaction's participation index in encrypted storage.

    Mirrors the :class:`CalculationRevision` catalogue repository: persistence is
    delegated to a :class:`SecureObjectRepository` at :class:`SensitivityClass`
    FINANCIAL under the active profile bucket, one secure object per
    ``transaction_id``. The participation index is critically sensitive financial
    data (it links a ledger transaction to its filings); no plaintext index is
    ever written to disk.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
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
        """Return the secure-object backend used by this repository."""
        return self._objects

    def exists(self, transaction_id: str) -> bool:
        """Report whether a participation index has been persisted for ``transaction_id``."""
        return self._objects.exists(PARTICIPATION_INDEX_NAMESPACE, derive_participation_index_id(transaction_id))

    def load(self, transaction_id: str) -> TransactionRevisionParticipationIndex:
        """Load and decrypt one transaction's persisted participation index.

        Returns an empty :class:`TransactionRevisionParticipationIndex` for that
        transaction when nothing has been persisted yet, rather than raising.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        object_key = derive_participation_index_id(transaction_id)
        try:
            record = self._objects.load(
                PARTICIPATION_INDEX_NAMESPACE,
                object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
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
        envelope = Envelope[TransactionRevisionParticipationIndex].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error("participation-index classification mismatch")
            raise TransactionParticipationIndexPersistenceError(
                "participation-index classification mismatch",
                translated_message=_PARTICIPATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if envelope.schema_version > PARTICIPATION_INDEX_SCHEMA_VERSION:
            _LOGGER.error("participation-index envelope version unsupported")
            raise TransactionParticipationIndexPersistenceError(
                "participation-index envelope version unsupported",
                translated_message=_PARTICIPATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": PARTICIPATION_INDEX_SCHEMA_VERSION,
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
        from ...adapters.persistence.storage import Envelope, SecureObjectWrite, SensitivityClass

        envelope = Envelope[TransactionRevisionParticipationIndex](
            schema_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=index,
        )
        return SecureObjectWrite(
            namespace=PARTICIPATION_INDEX_NAMESPACE,
            object_key=derive_participation_index_id(index.transaction_id),
            classification=SensitivityClass.FINANCIAL,
            schema_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


__all__ = [
    "PARTICIPATION_INDEX_NAMESPACE",
    "PARTICIPATION_INDEX_SCHEMA_VERSION",
    "TransactionParticipationIndexPersistenceError",
    "TransactionParticipationIndexRepository",
    "TransactionRevisionParticipation",
    "TransactionRevisionParticipationIndex",
    "derive_participation_index_id",
    "upsert_transaction_participation",
]
