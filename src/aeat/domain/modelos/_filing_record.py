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

import hashlib
import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._codes import ModeloCode
from ._errors import ModeloValidationError

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

_FilingRecordId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
_WorkUnitId = _FilingRecordId
_CalculationRevisionId = _FilingRecordId
_BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_Period = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16),
]
_ActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_Notes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
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
) -> str:
    """Deterministic 64-char SHA-256 id for a filing record.

    The id is content-addressed by the parent work unit, the filed
    calculation revision, the filing timestamp, and the actor. Two
    operators filing the same revision at the same instant produces
    the same id, which is impossible in practice — the timestamp
    guarantees uniqueness.
    """

    payload = {
        "work_unit_id": work_unit_id.strip(),
        "calculation_revision_id": calculation_revision_id.strip(),
        "filed_at": filed_at.isoformat(),
        "filed_by": filed_by.strip(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ModeloRecord(BaseModel):
    """Durable receipt of one internal filing event."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    filing_record_id: _FilingRecordId
    work_unit_id: _WorkUnitId
    calculation_revision_id: _CalculationRevisionId
    bucket_id: _BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: _Period
    filed_at: datetime
    filed_by: _ActorLabel
    notes: _Notes | None = None
    aeat_accepted: bool = False
    status: ModeloRecordStatus = ModeloRecordStatus.VIGENTE
    superseded_at: datetime | None = None
    superseded_by_filing_record_id: _FilingRecordId | None = None
    external_evidence: ExternalEvidence | None = None
    amends_filing_record_id: _FilingRecordId | None = None

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
        derived = derive_filing_record_id(
            work_unit_id=self.work_unit_id,
            calculation_revision_id=self.calculation_revision_id,
            filed_at=self.filed_at,
            filed_by=self.filed_by,
        )
        if derived != self.filing_record_id:
            raise ModeloValidationError(
                f"filing_record_id {self.filing_record_id!r} does not match the derived id {derived!r}"
            )
        if self.status is ModeloRecordStatus.VIGENTE:
            if self.superseded_at is not None or self.superseded_by_filing_record_id is not None:
                raise ModeloValidationError("current filing record must not carry supersession metadata")
        elif self.status is ModeloRecordStatus.SUPERSEDIDO:
            if self.superseded_at is None or self.superseded_by_filing_record_id is None:
                raise ModeloValidationError(
                    "superseded filing record must carry superseded_at and superseded_by_filing_record_id"
                )
            if self.superseded_at < self.filed_at:
                raise ModeloValidationError(
                    f"superseded_at {self.superseded_at.isoformat()} precedes filed_at {self.filed_at.isoformat()}"
                )
        return self


class ModeloRecordCatalogue(BaseModel):
    """Immutable catalogue of every filing record in storage."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    records: Mapping[str, ModeloRecord] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> ModeloRecordCatalogue:
        for key, record in self.records.items():
            if key != record.filing_record_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match filing_record_id {record.filing_record_id!r}"
                )
        # Exactly one CURRENT record per (bucket, modelo, year, period) tuple.
        currents: dict[tuple[str, str, int, str], str] = {}
        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            current_key = (record.bucket_id, record.modelo, record.filing_year, record.period)
            if current_key in currents:
                raise ModeloValidationError(
                    f"more than one current filing record for {current_key!r}: "
                    f"{currents[current_key]!r} and {record.filing_record_id!r}"
                )
            currents[current_key] = record.filing_record_id
        return self

    def get(self, filing_record_id: str) -> ModeloRecord | None:
        return self.records.get(filing_record_id)

    def current_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> ModeloRecord | None:
        """Return the current (non-superseded) filing record for a tuple.

        Returns ``None`` when no filing has ever happened for the
        tuple. Returns the active filing record when one exists. Never
        returns a superseded record — callers must iterate
        :attr:`records` directly to walk audit history.
        """

        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            if (
                record.bucket_id == bucket_id
                and record.modelo == modelo
                and record.filing_year == filing_year
                and record.period == period
            ):
                return record
        return None

    def history_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> tuple[ModeloRecord, ...]:
        """Return every filing record for a tuple, ordered by filed_at."""

        matching = tuple(
            record
            for record in self.records.values()
            if record.bucket_id == bucket_id
            and record.modelo == modelo
            and record.filing_year == filing_year
            and record.period == period
        )
        return tuple(sorted(matching, key=lambda r: r.filed_at))

    def values(self):
        return self.records.values()

    def __iter__(self) -> Iterator[ModeloRecord]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        return iter(self.records.values())

    def __len__(self) -> int:
        return len(self.records)

    def __contains__(self, key: object) -> bool:
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
