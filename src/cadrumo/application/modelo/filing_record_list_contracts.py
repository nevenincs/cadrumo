"""Bounded exact-profile filing receipt list contracts and canonical projection validation."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.time.utc import validate_utc_aware
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
)
from ...domain.modelos.filing_text import FilingNotes, ModeloActorLabel
from ..operations.models import CredentialFreeOperationRequest

MAX_MODELO_FILING_RECORD_LIST_ROWS = 4_096


_BoundedPeriod = Annotated[str, Field(min_length=1, max_length=16)]


_BoundedMemberNif = Annotated[str, Field(min_length=1, max_length=32)]


_ModeloCodeValue = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")]


_EvidenceReferenceValue = Annotated[str, StringConstraints(min_length=1, max_length=128)]


_CsvValue = Annotated[
    str,
    StringConstraints(
        min_length=AEAT_CSV_MIN_LENGTH,
        max_length=AEAT_CSV_MAX_LENGTH,
        pattern=rf"^[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}$",
    ),
]


_PresentationValue = Annotated[str, Field(max_length=64)]


_TipoSolicitudValue = Annotated[str, Field(min_length=1, max_length=64)]


class ModeloFilingRecordRegisterProjection(BaseModel):
    """Bounded AEAT register identifiers carried by the CLI filing row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    expediente_id: _EvidenceReferenceValue | None = None
    csv: _CsvValue | None = None
    justificante_number: _PresentationValue | None = None
    tipo_solicitud: _TipoSolicitudValue | None = None
    presented_at: datetime | None = None

    @field_validator("presented_at")
    @classmethod
    @pydantic_validation_boundary
    def _presented_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _has_register_identity(self) -> Self:
        if self.expediente_id is None and self.csv is None:
            raise ValueError("an AEAT register reference needs an expediente id or a CSV")
        return self


class ModeloFilingRecordEvidenceProjection(BaseModel):
    """Bounded external-evidence metadata without evidence bytes or locators."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: ExternalEvidenceKind
    reference_id: _EvidenceReferenceValue
    imported_at: datetime

    @field_validator("imported_at")
    @classmethod
    @pydantic_validation_boundary
    def _imported_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


class ModeloFilingRecordListRequest(CredentialFreeOperationRequest):
    """Select one profile's complete filing history or one modelo."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    modelo: _ModeloCodeValue | None = None
    include_superseded: bool = False


class ModeloFilingRecordListEntryProjection(BaseModel):
    """Allowlisted wire fields already exposed by the filing-record CLI."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: _ModeloCodeValue
    filing_year: FilingYear
    period: _BoundedPeriod
    filed_at: datetime
    filed_by: ModeloActorLabel
    member_nif: _BoundedMemberNif | None
    notes: FilingNotes | None
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    aeat_register: ModeloFilingRecordRegisterProjection | None
    aeat_accepted: bool
    status: ModeloRecordStatus
    superseded_at: datetime | None
    superseded_by_filing_record_id: FilingRecordId | None
    external_evidence: ModeloFilingRecordEvidenceProjection | None
    amends_filing_record_id: FilingRecordId | None
    kind: Literal["internal_filing"] = "internal_filing"
    live_submission: Literal[False] = False

    @field_validator("filed_at", "superseded_at")
    @classmethod
    @pydantic_validation_boundary
    def _filing_timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _ground_public_fields(self) -> Self:
        Period.from_year_and_code(self.filing_year, self.period)
        confirmed = self.confirmation is AeatConfirmationState.CONFIRMADA
        if self.aeat_accepted != confirmed or self.aeat_accepted != (self.external_evidence is not None):
            raise ValueError("AEAT acceptance must match confirmation and external evidence")
        if self.status is ModeloRecordStatus.VIGENTE:
            if self.superseded_at is not None or self.superseded_by_filing_record_id is not None:
                raise ValueError("current filing record must not carry supersession metadata")
        elif self.superseded_at is None or self.superseded_by_filing_record_id is None:
            raise ValueError("superseded filing record must carry supersession metadata")
        elif self.superseded_at < self.filed_at:
            raise ValueError("superseded_at must not precede filed_at")
        return self

    @classmethod
    def from_record(cls, record: ModeloRecord) -> ModeloFilingRecordListEntryProjection:
        """Copy only the stable list payload fields from a canonical receipt."""
        return cls(
            filing_record_id=record.filing_record_id,
            work_unit_id=record.work_unit_id,
            calculation_revision_id=record.calculation_revision_id,
            bucket_id=record.bucket_id,
            modelo=str(record.modelo),
            filing_year=record.filing_year,
            period=record.period.registry_token,
            filed_at=record.filed_at,
            filed_by=record.filed_by,
            member_nif=record.member_nif,
            notes=record.notes,
            origin=record.origin,
            confirmation=record.confirmation,
            declaration_kind=record.declaration_kind,
            aeat_register=(
                ModeloFilingRecordRegisterProjection.model_validate(record.aeat_register.model_dump(mode="python"))
                if record.aeat_register is not None
                else None
            ),
            aeat_accepted=record.aeat_accepted,
            status=record.status,
            superseded_at=record.superseded_at,
            superseded_by_filing_record_id=record.superseded_by_filing_record_id,
            external_evidence=(
                ModeloFilingRecordEvidenceProjection.model_validate(record.external_evidence.model_dump(mode="python"))
                if record.external_evidence is not None
                else None
            ),
            amends_filing_record_id=record.amends_filing_record_id,
        )


_Rows = Annotated[
    tuple[ModeloFilingRecordListEntryProjection, ...],
    Field(max_length=MAX_MODELO_FILING_RECORD_LIST_ROWS),
]


class ModeloFilingRecordListProjection(BaseModel):
    """Complete, bounded result for one exact-profile filing-record listing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    modelo: _ModeloCodeValue | None
    include_superseded: bool
    record_count: NonNegativeInt
    records: _Rows

    @model_validator(mode="after")
    def _correlate_rows(self) -> Self:
        """Reject cross-profile, out-of-filter, duplicate, or noncanonical rows."""
        if self.record_count != len(self.records):
            raise ValueError("filing record count does not match its rows")
        _require_filing_list_filter(self)
        if len({record.filing_record_id for record in self.records}) != len(self.records):
            raise ValueError("filing record list repeats an identity")
        expected = tuple(sorted(self.records, key=_projection_order_key))
        if self.records != expected:
            raise ValueError("filing record list is not in canonical order")
        return self


def _require_filing_list_filter(projection: ModeloFilingRecordListProjection) -> None:
    """Reject foreign-profile rows before modelo and supersession filters."""
    profile_id = str(projection.profile_id)
    if any(record.bucket_id != profile_id for record in projection.records):
        raise ValueError("filing record list contains another profile")
    if projection.modelo is not None and any(record.modelo != projection.modelo for record in projection.records):
        raise ValueError("filing record list exceeds its modelo filter")
    if not projection.include_superseded and any(
        record.status is not ModeloRecordStatus.VIGENTE for record in projection.records
    ):
        raise ValueError("filing record list contains superseded rows")


def _projection_order_key(
    record: ModeloFilingRecordListEntryProjection,
) -> tuple[str, int, str, str, datetime, str]:
    return (
        record.bucket_id,
        record.filing_year,
        str(record.modelo),
        record.period,
        record.filed_at,
        record.filing_record_id,
    )
