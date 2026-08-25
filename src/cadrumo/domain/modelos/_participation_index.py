"""Transaction-to-revision participation index for audit cross-reference.

The ledger persists only the forward link: a :class:`CalculationRevision`
names its ``source_transaction_ids``. The inverse question an auditor asks of a
single ledger transaction — which finalized modelo revisions, filings, and
justificantes consumed it — has no persisted, surfaced answer; the only inverse
traversal is the transient ``blocking_modelo_references`` write-guard scan.

This module introduces the :class:`TransactionRevisionParticipationIndex`, a
derived, rebuildable secure-object recording, per ledger transaction id, the set
of finalized-revision participations: the ``calculation_revision_id``,
``work_unit_id``, ``modelo``, ``filing_year``, ``period`` and ``revision_state``,
plus, where the revision is filed, the ``filing_record_id`` and the
justificante reference. The index is co-written atomically inside the same
``save_with_secure_object_writes`` unit of work that persists the revision (per
the composition-service single-writer discipline); it is a read-side cache, never
a second source of truth, and is fully rebuildable from the revision catalogue.

The index is keyed by ``transaction_id`` and persisted one secure
:class:`~cadrumo.adapters.persistence.storage.Envelope` per transaction, so a
revision over N contributing transactions co-emits N index upserts. Each upsert
merges its new participation into that transaction's entry without disturbing
the participations already recorded for it.

See :func:`derive_participation_index_id` for the object-key grammar, and the
``TransactionParticipationIndexRepository`` for the encrypted persistence
boundary mirroring the :class:`CalculationRevision` catalogue repository at
:class:`~cadrumo.adapters.persistence.storage.SensitivityClass` FINANCIAL.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError, model_validator

from ...core import Period
from ...core.identity import CalculationRevisionId, FilingRecordId, TransactionId, WorkUnitId
from ._codes import ModeloCode
from .errors import ModeloError, ModeloValidationError

_JustificanteReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_RevisionState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_STRING_KEYED_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object], config=ConfigDict(strict=True)
)


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
        try:
            mapping = _STRING_KEYED_MAPPING_ADAPTER.validate_python(data)
        except ValidationError:
            return data
        if "modelo" in mapping:
            value = mapping["modelo"]
            if isinstance(value, str) and not isinstance(value, ModeloCode):
                mapping["modelo"] = ModeloCode(value)
            return mapping
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
    """Return a new :class:`TransactionRevisionParticipationIndex` with ``participation`` merged.

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


__all__ = [
    "TransactionParticipationIndexPersistenceError",
    "TransactionRevisionParticipation",
    "TransactionRevisionParticipationIndex",
    "derive_participation_index_id",
    "upsert_transaction_participation",
]
