"""Filing-record store paired with filed calculation revisions.

A :class:`ModeloRecord` is the durable receipt of an internal filing
event: at time T, actor A marked calculation revision R of work unit
W as the current filed answer for (bucket, modelo, year, period).
The filing record holds filing-event state (filed timestamp, actor,
notes, AEAT-acceptance bit, supersession link); the filed calculation
revision holds the immutable calculation result. The two are paired
so the calculation revision never accretes filing-side concerns.

There is at most one *current* filing record per (bucket_id, modelo,
filing_year, period) tuple. When a later verified revision is filed,
the previous current record is superseded — its
``superseded_by_filing_record_id`` is set, the calculation revision
it pointed at moves from ``FILED`` to ``FILED_SUPERSEDED``, and the
new filing record becomes current. Both records remain in the
catalogue for audit.

The ``aeat_accepted`` flag defaults to ``False`` and is independent
of internal filing. It exists only to record an externally-observed
AEAT acceptance imported into the bucket through read-only live
signals. The filing record itself never initiates a live submission.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self, override

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ...core import Period
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ._codes import ModeloCode
from ._errors import ModeloValidationError
from ._ids import CalculationRevisionId, FilingRecordId, WorkUnitId

ModeloActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
"""Validated string identifying the operator who filed or triggered a filing event.

Strips surrounding whitespace; must be 1–64 characters after stripping.
Used as ``filed_by`` on :class:`ModeloRecord` and feeds into the
content-addressed :func:`derive_filing_record_id`.
"""
_Notes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_MemberNif = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


class ModeloRecordStatus(StrEnum):
    """Closed enumeration of filing-record lifecycle states.

    * ``VIGENTE`` — the record is the currently-effective filed answer
      for its (bucket, modelo, year, period) tuple.
    * ``SUPERSEDIDO`` — a later filing replaced this one. The record
      remains for audit; ``superseded_by_filing_record_id`` points
      at the successor.
    """

    VIGENTE = "vigente"
    SUPERSEDIDO = "supersedido"


class ExternalEvidenceKind(StrEnum):
    """Closed catalogue of external-evidence kinds.

    A filing record marked with one of these kinds carries imported
    official evidence (an AEAT justificante PDF, a CSV-attested
    receipt) rather than a tool-computed calculation revision. This
    is the gate the modelo-amend path requires before it accepts an
    amendment baseline.
    """

    AEAT_JUSTIFICANTE_PDF = "aeat_justificante_pdf"
    AEAT_CSV_REGISTER = "aeat_csv_register"
    AEAT_LIVE_CAPTURE = "aeat_live_capture"


_EvidenceReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ExternalEvidence(BaseModel):
    """Imported-evidence metadata for an externally-filed return.

    Populated by the filing-record import path (justificante reader,
    CSV register importer, AEAT live capture); consumed by the
    modelo-amend path as the gate that proves the baseline is
    AEAT-attested and not a fabricated local draft.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: ExternalEvidenceKind
    reference_id: _EvidenceReference
    imported_at: datetime


def derive_filing_record_id(
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    filed_at: datetime,
    filed_by: str,
    member_nif: str | None = None,
) -> str:
    """Deterministic 64-char SHA-256 id for a filing record.

    The id is content-addressed by the parent work unit, the filed
    calculation revision, the filing timestamp, and the actor. Two
    operators filing the same revision at the same instant produce
    the same id, which is impossible in practice because the timestamp
    guarantees uniqueness. Member-scoped group filings include the
    member NIF in the identity; single-filer records omit it so legacy
    record ids remain stable.
    """
    payload = {
        "work_unit_id": work_unit_id.strip(),
        "calculation_revision_id": calculation_revision_id.strip(),
        "filed_at": filed_at.isoformat(),
        "filed_by": filed_by.strip(),
    }
    if member_nif is not None:
        payload["member_nif"] = member_nif.strip()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_hex(encoded)


class ModeloRecord(BaseModel):
    """Durable receipt of one internal filing event for an AEAT modelo (tax form).

    Pairs a filed :class:`CalculationRevisionId` with the filing event
    metadata (actor, timestamp, notes, AEAT-acceptance bit, supersession
    link). The id is content-addressed by ``work_unit_id``,
    ``calculation_revision_id``, ``filed_at``, and ``filed_by`` via
    :func:`derive_filing_record_id`; a ``model_validator`` enforces the
    derivation on construction.

    ``aeat_accepted`` records an externally-observed AEAT acceptance
    signal imported through read-only live signals — it does not imply
    that the application submitted anything.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: Period
    member_nif: _MemberNif | None = None
    filed_at: datetime
    filed_by: ModeloActorLabel
    notes: _Notes | None = None
    aeat_accepted: bool = False
    status: ModeloRecordStatus = ModeloRecordStatus.VIGENTE
    superseded_at: datetime | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidence | None = None
    amends_filing_record_id: FilingRecordId | None = None
    # Denormalised footprint of the filed revision's contributing ledger
    # transactions, so an external audit tool holding only a filing record
    # resolves its transaction set in one hop. Deliberately EXCLUDED from
    # ``derive_filing_record_id`` (mirroring the ledger_filing_snapshot exclusion
    # on the revision hash) so the content address is unaffected; defaults to ()
    # for non-ledger filings.
    source_transaction_ids: tuple[str, ...] = ()

    @field_validator("modelo", mode="before")
    @classmethod
    def _coerce_modelo(cls, value: object) -> ModeloCode:
        if isinstance(value, ModeloCode):
            return value
        if isinstance(value, str):
            return ModeloCode(value)
        raise ModeloValidationError(f"expected ModeloCode or str, got {type(value).__name__}")

    @model_validator(mode="after")
    def _enforce_invariants(self) -> ModeloRecord:
        if self.period.filing_year != self.filing_year:
            raise ModeloValidationError(
                f"filing_year {self.filing_year!r} does not match period year {self.period.filing_year!r}",
            )
        derived = derive_filing_record_id(
            work_unit_id=self.work_unit_id,
            calculation_revision_id=self.calculation_revision_id,
            filed_at=self.filed_at,
            filed_by=self.filed_by,
            member_nif=self.member_nif,
        )
        if derived != self.filing_record_id:
            raise ModeloValidationError(
                f"filing_record_id {self.filing_record_id!r} does not match the derived id {derived!r}",
            )
        if self.aeat_accepted and self.external_evidence is None:
            raise ModeloValidationError("AEAT-accepted filing record must carry external evidence")
        if self.external_evidence is not None and not self.aeat_accepted:
            raise ModeloValidationError("external filing evidence must carry AEAT acceptance")
        if self.status is ModeloRecordStatus.VIGENTE:
            if self.superseded_at is not None or self.superseded_by_filing_record_id is not None:
                raise ModeloValidationError("current filing record must not carry supersession metadata")
        elif self.status is ModeloRecordStatus.SUPERSEDIDO:
            if self.superseded_at is None or self.superseded_by_filing_record_id is None:
                raise ModeloValidationError(
                    "superseded filing record must carry superseded_at and superseded_by_filing_record_id",
                )
            if self.superseded_at < self.filed_at:
                raise ModeloValidationError(
                    f"superseded_at {self.superseded_at.isoformat()} precedes filed_at {self.filed_at.isoformat()}",
                )
        return self

    @override
    def model_copy(self, *, update: Mapping[str, object] | None = None, deep: bool = False) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        if update:
            return type(self).model_validate(copied.model_dump(mode="python"))
        return copied


class ModeloRecordCatalogue(BaseModel):
    """Immutable catalogue of every filing record in a bucket's storage.

    Keyed by ``filing_record_id``; the model validator enforces that every
    key equals the id of the :class:`ModeloRecord` it maps to, and that at
    most one record per (bucket_id, modelo, filing_year, period,
    member_nif) tuple carries ``status=VIGENTE``. Iteration yields
    :class:`ModeloRecord` values (not key–value pairs) — the override is
    annotated with a suppression comment on ``__iter__``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    records: Mapping[str, ModeloRecord] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> ModeloRecordCatalogue:
        for key, record in self.records.items():
            if key != record.filing_record_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match filing_record_id {record.filing_record_id!r}",
                )
        # Exactly one CURRENT record per (bucket, modelo, year, period, member) tuple.
        currents: dict[tuple[str, str, int, Period, str | None], str] = {}
        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            current_key = (
                record.bucket_id,
                record.modelo,
                record.filing_year,
                record.period,
                record.member_nif,
            )
            if current_key in currents:
                raise ModeloValidationError(
                    f"more than one current filing record for {current_key!r}: "
                    f"{currents[current_key]!r} and {record.filing_record_id!r}",
                )
            currents[current_key] = record.filing_record_id
        return self

    def get(self, filing_record_id: str) -> ModeloRecord | None:
        """Return the :class:`ModeloRecord` for ``filing_record_id``, or ``None``."""
        return self.records.get(filing_record_id)

    def current_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> ModeloRecord | None:
        """Return the current (non-superseded) :class:`ModeloRecord` for a filing tuple.

        Returns ``None`` when no filing has ever happened for the
        tuple. ``member_nif=None`` means the single-filer or aggregate
        record, not every member. Returns the active filing record when
        one exists. Never returns a superseded record — callers must
        iterate :attr:`records` directly to walk audit history.
        """
        expected_member_nif = member_nif.strip() if member_nif is not None else None
        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            if (
                record.bucket_id == bucket_id
                and record.modelo == modelo
                and record.filing_year == filing_year
                and record.period == period
                and record.member_nif == expected_member_nif
            ):
                return record
        return None

    def history_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> tuple[ModeloRecord, ...]:
        """Return every filing record for a tuple, ordered by filed_at.

        Returns:
            Tuple of :class:`ModeloRecord` objects ordered by filing timestamp.
        """
        expected_member_nif = member_nif.strip() if member_nif is not None else None
        matching = tuple(
            record
            for record in self.records.values()
            if record.bucket_id == bucket_id
            and record.modelo == modelo
            and record.filing_year == filing_year
            and record.period == period
            and record.member_nif == expected_member_nif
        )
        return tuple(sorted(matching, key=lambda r: r.filed_at))

    def values(self):
        """Return a view of all :class:`ModeloRecord` values in the catalogue."""
        return self.records.values()

    @override
    def __iter__(self) -> Iterator[ModeloRecord]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        """Iterate over :class:`ModeloRecord` values (not ``(key, value)`` pairs)."""
        return iter(self.records.values())

    def __len__(self) -> int:
        """Return the number of filing records in the catalogue."""
        return len(self.records)

    def __contains__(self, key: object) -> bool:
        """Test membership by :class:`ModeloRecord` instance or ``filing_record_id`` string."""
        if isinstance(key, ModeloRecord):
            return key.filing_record_id in self.records
        if isinstance(key, str):
            return key in self.records
        return False


__all__ = [
    "ExternalEvidence",
    "ExternalEvidenceKind",
    "ModeloRecord",
    "ModeloRecordCatalogue",
    "ModeloRecordStatus",
    "derive_filing_record_id",
]
