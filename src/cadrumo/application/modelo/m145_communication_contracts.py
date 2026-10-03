"""Typed request and encrypted result contracts for Modelo 145 operations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.hashing import sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...domain.calculations.registry.fixed_width_codec import ExportEncoding
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .m145_communication_period import M145CommunicationPeriod
from .m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordState,
    M145CommunicationValidationIssue,
    M145CommunicationValidationIssueKind,
    M145CommunicationValidationResult,
)

type M145CommunicationOperationId = Literal[
    "modelo.m145.create",
    "modelo.m145.validate",
    "modelo.m145.export",
    "modelo.m145.mark_delivered_to_payer",
    "modelo.m145.mark_locally_completed",
]

M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: M145CommunicationOperationId = "modelo.m145.create"

M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: M145CommunicationOperationId = "modelo.m145.validate"

M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: M145CommunicationOperationId = "modelo.m145.export"

M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: M145CommunicationOperationId = (
    "modelo.m145.mark_delivered_to_payer"
)

M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: M145CommunicationOperationId = (
    "modelo.m145.mark_locally_completed"
)

M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE = "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND"

type M145CommunicationRefusalCode = Literal[
    "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND",
    "REFUSED_M145_COMMUNICATION_RECORD_AMBIGUOUS",
    "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION",
    "REFUSED_M145_COMMUNICATION_RECORD_EXPORT",
    "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION",
]

M145_COMMUNICATION_OPERATION_IDS: tuple[M145CommunicationOperationId, ...] = (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
)

_NOT_FOUND_REFUSAL_CODE: M145CommunicationRefusalCode = M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE

_AMBIGUOUS_REFUSAL_CODE: M145CommunicationRefusalCode = "REFUSED_M145_COMMUNICATION_RECORD_AMBIGUOUS"

_VALIDATION_REFUSAL_CODE: M145CommunicationRefusalCode = "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION"

_EXPORT_REFUSAL_CODE: M145CommunicationRefusalCode = "REFUSED_M145_COMMUNICATION_RECORD_EXPORT"

_TRANSITION_REFUSAL_CODE: M145CommunicationRefusalCode = "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION"

M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION: dict[
    M145CommunicationOperationId, frozenset[M145CommunicationRefusalCode]
] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: frozenset({_NOT_FOUND_REFUSAL_CODE, _VALIDATION_REFUSAL_CODE}),
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: frozenset(
        {_NOT_FOUND_REFUSAL_CODE, _AMBIGUOUS_REFUSAL_CODE, _VALIDATION_REFUSAL_CODE}
    ),
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: frozenset(
        {_NOT_FOUND_REFUSAL_CODE, _AMBIGUOUS_REFUSAL_CODE, _VALIDATION_REFUSAL_CODE, _EXPORT_REFUSAL_CODE}
    ),
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: frozenset(
        {_NOT_FOUND_REFUSAL_CODE, _AMBIGUOUS_REFUSAL_CODE, _VALIDATION_REFUSAL_CODE}
    ),
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: frozenset(
        {_NOT_FOUND_REFUSAL_CODE, _AMBIGUOUS_REFUSAL_CODE, _VALIDATION_REFUSAL_CODE, _TRANSITION_REFUSAL_CODE}
    ),
}

M145_COMMUNICATION_REFUSAL_CODE_BY_VALUE: dict[str, M145CommunicationRefusalCode] = {
    code: code for codes in M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION.values() for code in codes
}

_MAX_SELECTOR_LENGTH = 256

_MAX_CONTEXT_FACTS = 32

_MAX_CONTEXT_VALUE_LENGTH = 32768

_MAX_REFUSAL_MESSAGE_LENGTH = 32768

_M145Year = Annotated[int, Field(ge=2012, le=2099)]


def _canonical_m145_identity(
    service_owner: str,
    modelo: str,
) -> tuple[Literal["cadrumo.application.modelo"], Literal["145"]]:
    if service_owner != "cadrumo.application.modelo" or modelo != "145":
        raise ValueError("M145 projection requires the canonical service owner and modelo")
    return service_owner, modelo


class M145CommunicationOperationRecordNotFoundError(M145CommunicationRecordNotFoundError):
    """The canonical record lookup missed before this operation could write."""


class M145CommunicationFieldValueProjection(BaseModel):
    """One field/value pair preserved across encrypted operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    value: Annotated[str, Field(max_length=512)]


class M145CommunicationCreateRequest(BaseModel):
    """Sensitive create intent held only as a secure operation reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    communication_year: _M145Year
    period_token: M145CommunicationPeriod
    field_values: Annotated[tuple[M145CommunicationFieldValueProjection, ...], Field(min_length=1, max_length=256)]
    note: Annotated[str, Field(max_length=512)] | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def _field_values_are_unique_and_sorted(self) -> M145CommunicationCreateRequest:
        identifiers = tuple(str(item.casilla_id) for item in self.field_values)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("M145 operation field values must be unique and sorted by casilla id")
        return self

    @classmethod
    def from_command(
        cls,
        *,
        profile_id: UUID,
        command: M145CommunicationCreateCommand,
        actor: str,
    ) -> M145CommunicationCreateRequest:
        """Copy the canonical parsed CLI command into an immutable request."""
        return cls(
            profile_id=profile_id,
            communication_year=command.communication_year,
            period_token=command.period_token,
            field_values=tuple(
                M145CommunicationFieldValueProjection(casilla_id=key, value=value)
                for key, value in sorted(command.field_values.items(), key=lambda pair: str(pair[0]))
            ),
            note=command.note,
            actor=actor,
        )

    def to_command(self) -> M145CommunicationCreateCommand:
        """Restore the existing service command without changing field values."""
        return M145CommunicationCreateCommand(
            communication_year=self.communication_year,
            period_token=self.period_token,
            field_values={item.casilla_id: item.value for item in self.field_values},
            note=self.note,
        )


class _M145RecordSelectionRequest(BaseModel):
    """Exact-profile record selector used by the four existing read/action verbs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    communication_record_id: Annotated[str, Field(min_length=1, max_length=_MAX_SELECTOR_LENGTH)]


class M145CommunicationValidateRequest(_M145RecordSelectionRequest):
    """Read-only validation of one full record id or existing prefix."""


class M145CommunicationExportRequest(_M145RecordSelectionRequest):
    """Registry-layout export of one full record id or existing prefix."""

    actor: Annotated[str, Field(min_length=1, max_length=64)]


class M145CommunicationMarkDeliveredRequest(_M145RecordSelectionRequest):
    """Mark one valid communication as delivered to its payer."""

    actor: Annotated[str, Field(min_length=1, max_length=64)]


class M145CommunicationMarkCompletedRequest(_M145RecordSelectionRequest):
    """Mark one payer-delivered communication as locally completed."""

    actor: Annotated[str, Field(min_length=1, max_length=64)]


type M145CommunicationRequest = (
    M145CommunicationCreateRequest
    | M145CommunicationValidateRequest
    | M145CommunicationExportRequest
    | M145CommunicationMarkDeliveredRequest
    | M145CommunicationMarkCompletedRequest
)


class M145CommunicationRecordProjection(BaseModel):
    """Complete canonical record data required by the existing CLI renderer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["record"] = "record"
    communication_record_id: Hex64Str
    bucket_id: BucketId
    service_owner: Literal["cadrumo.application.modelo"]
    modelo: Literal["145"]
    communication_year: _M145Year
    period_token: M145CommunicationPeriod
    revision_id: RevisionId
    state: M145CommunicationRecordState
    field_values: Annotated[tuple[M145CommunicationFieldValueProjection, ...], Field(min_length=1, max_length=256)]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    created_at: datetime
    delivered_to_payer_at: datetime | None
    locally_completed_at: datetime | None
    note: Annotated[str, Field(max_length=512)] | None

    @model_validator(mode="after")
    def _field_values_are_unique_and_sorted(self) -> M145CommunicationRecordProjection:
        identifiers = tuple(str(item.casilla_id) for item in self.field_values)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("M145 projection field values must be unique and sorted by casilla id")
        return self

    @classmethod
    def from_record(cls, record: M145CommunicationRecord) -> M145CommunicationRecordProjection:
        """Retain every persisted field and its canonical ordering."""
        service_owner, modelo = _canonical_m145_identity(record.service_owner, record.modelo)
        return cls(
            communication_record_id=record.communication_record_id,
            bucket_id=record.bucket_id,
            service_owner=service_owner,
            modelo=modelo,
            communication_year=record.communication_year,
            period_token=record.period_token,
            revision_id=record.revision_id,
            state=record.state,
            field_values=tuple(
                M145CommunicationFieldValueProjection(casilla_id=key, value=value)
                for key, value in sorted(record.field_values.items(), key=lambda pair: str(pair[0]))
            ),
            legal_refs=tuple(record.legal_refs),
            source_refs=tuple(record.source_refs),
            created_at=record.created_at,
            delivered_to_payer_at=record.delivered_to_payer_at,
            locally_completed_at=record.locally_completed_at,
            note=record.note,
        )

    def to_record(self) -> M145CommunicationRecord:
        """Restore the canonical immutable record for the established CLI payload."""
        return M145CommunicationRecord(
            communication_record_id=self.communication_record_id,
            bucket_id=self.bucket_id,
            service_owner=self.service_owner,
            modelo=self.modelo,
            communication_year=self.communication_year,
            period_token=self.period_token,
            revision_id=self.revision_id,
            state=self.state,
            field_values={item.casilla_id: item.value for item in self.field_values},
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
            created_at=self.created_at,
            delivered_to_payer_at=self.delivered_to_payer_at,
            locally_completed_at=self.locally_completed_at,
            note=self.note,
        )


class M145CommunicationValidationIssueProjection(BaseModel):
    """All human-facing details and authority references for one finding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: M145CommunicationValidationIssueKind
    casilla_id: CasillaId | None
    data_type: str | None
    message: Annotated[str, Field(min_length=1, max_length=512)]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @classmethod
    def from_issue(
        cls,
        issue: M145CommunicationValidationIssue,
    ) -> M145CommunicationValidationIssueProjection:
        """Copy one canonical issue without reducing or reordering its refs."""
        return cls(
            kind=issue.kind,
            casilla_id=issue.casilla_id,
            data_type=issue.data_type,
            message=issue.message,
            legal_refs=tuple(issue.legal_refs),
            source_refs=tuple(issue.source_refs),
        )

    def to_issue(self) -> M145CommunicationValidationIssue:
        """Restore the issue required by the existing CLI rendering module."""
        return M145CommunicationValidationIssue(
            kind=self.kind,
            casilla_id=self.casilla_id,
            data_type=self.data_type,
            message=self.message,
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
        )


class M145CommunicationValidationProjection(BaseModel):
    """Complete typed validation result, including ordered issue provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["validation"] = "validation"
    schema_version: Literal["1"] = "1"
    communication_record_id: Hex64Str
    bucket_id: BucketId
    service_owner: Literal["cadrumo.application.modelo"]
    modelo: Literal["145"]
    communication_year: _M145Year
    period_token: M145CommunicationPeriod
    revision_id: RevisionId
    valid: bool
    issue_count: int = Field(ge=0)
    issues: tuple[M145CommunicationValidationIssueProjection, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @model_validator(mode="after")
    def _issue_count_matches(self) -> M145CommunicationValidationProjection:
        if self.issue_count != len(self.issues) or self.valid != (self.issue_count == 0):
            raise ValueError("M145 validation projection must preserve its canonical issue count and validity")
        return self

    @classmethod
    def from_result(cls, result: M145CommunicationValidationResult) -> M145CommunicationValidationProjection:
        """Copy the complete canonical result with its finding order intact."""
        service_owner, modelo = _canonical_m145_identity(result.service_owner, result.modelo)
        return cls(
            communication_record_id=result.communication_record_id,
            bucket_id=result.bucket_id,
            service_owner=service_owner,
            modelo=modelo,
            communication_year=result.communication_year,
            period_token=result.period_token,
            revision_id=result.revision_id,
            valid=result.valid,
            issue_count=result.issue_count,
            issues=tuple(M145CommunicationValidationIssueProjection.from_issue(issue) for issue in result.issues),
            legal_refs=tuple(result.legal_refs),
            source_refs=tuple(result.source_refs),
        )

    def to_result(self) -> M145CommunicationValidationResult:
        """Restore the canonical result consumed by the existing CLI renderer."""
        return M145CommunicationValidationResult(
            communication_record_id=self.communication_record_id,
            bucket_id=self.bucket_id,
            service_owner=self.service_owner,
            modelo=self.modelo,
            communication_year=self.communication_year,
            period_token=self.period_token,
            revision_id=self.revision_id,
            valid=self.valid,
            issue_count=self.issue_count,
            issues=tuple(issue.to_issue() for issue in self.issues),
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
        )


class M145CommunicationExportProjection(BaseModel):
    """Full export response; payload stays in encrypted operation result custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["export"] = "export"
    schema_version: Literal["1"] = "1"
    communication_record_id: Hex64Str
    bucket_id: BucketId
    service_owner: Literal["cadrumo.application.modelo"]
    modelo: Literal["145"]
    communication_year: _M145Year
    period_token: M145CommunicationPeriod
    revision_id: RevisionId
    export_layout_id: Annotated[str, Field(min_length=1, max_length=256)]
    encoding: ExportEncoding
    record_count: int = Field(ge=1)
    byte_length: int = Field(ge=1)
    payload_sha256: ContentDigest
    payload_text: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @model_validator(mode="after")
    def _receipt_describes_payload(self) -> M145CommunicationExportProjection:
        payload = self.payload_text.encode(self.encoding.value)
        if self.byte_length != len(payload):
            raise ValueError("M145 export byte length does not match the encrypted result payload")
        if self.payload_sha256 != sha256_hex(payload):
            raise ValueError("M145 export digest does not match the encrypted result payload")
        return self

    @classmethod
    def from_result(cls, result: M145CommunicationExportResult) -> M145CommunicationExportProjection:
        """Copy both the complete local payload and its canonical receipt."""
        service_owner, modelo = _canonical_m145_identity(result.service_owner, result.modelo)
        return cls(
            communication_record_id=result.communication_record_id,
            bucket_id=result.bucket_id,
            service_owner=service_owner,
            modelo=modelo,
            communication_year=result.communication_year,
            period_token=result.period_token,
            revision_id=result.revision_id,
            export_layout_id=result.export_layout_id,
            encoding=ExportEncoding(result.encoding),
            record_count=result.record_count,
            byte_length=result.byte_length,
            payload_sha256=result.payload_sha256,
            payload_text=result.payload.decode(result.encoding),
            legal_refs=tuple(result.legal_refs),
            source_refs=tuple(result.source_refs),
        )

    def to_result(self) -> M145CommunicationExportResult:
        """Restore the canonical payload for the established CLI formatter."""
        return M145CommunicationExportResult(
            communication_record_id=self.communication_record_id,
            bucket_id=self.bucket_id,
            service_owner=self.service_owner,
            modelo=self.modelo,
            communication_year=self.communication_year,
            period_token=self.period_token,
            revision_id=self.revision_id,
            export_layout_id=self.export_layout_id,
            encoding=self.encoding,
            record_count=self.record_count,
            byte_length=self.byte_length,
            payload_sha256=self.payload_sha256,
            payload=self.payload_text.encode(self.encoding.value),
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
        )


class M145CommunicationErrorContextFact(BaseModel):
    """One already-scrubbed context entry from a canonical refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: Annotated[str, Field(min_length=1, max_length=128)]
    value: Annotated[str, Field(max_length=_MAX_CONTEXT_VALUE_LENGTH)]


class M145CommunicationRefusalProjection(BaseModel):
    """Correlated, bounded pre-write refusal detail stored as an encrypted operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: M145CommunicationRefusalCode
    message: Annotated[str, Field(min_length=1, max_length=_MAX_REFUSAL_MESSAGE_LENGTH)]
    context: Annotated[tuple[M145CommunicationErrorContextFact, ...], Field(max_length=_MAX_CONTEXT_FACTS)]


type M145CommunicationOutputProjection = Annotated[
    M145CommunicationRecordProjection | M145CommunicationValidationProjection | M145CommunicationExportProjection,
    Field(discriminator="kind"),
]


class M145CommunicationOperationResult(BaseModel):
    """Terminal projected result or typed refusal tied to one exact operation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: M145CommunicationOperationId
    outcome: Literal["completed", "prewrite_refusal"]
    effect: OperationEffect
    result: M145CommunicationOutputProjection | None = None
    refusal: M145CommunicationRefusalProjection | None = None

    @model_validator(mode="after")
    def _complete_projection(self) -> M145CommunicationOperationResult:
        if self.outcome == "completed":
            if self.result is None or self.refusal is not None:
                raise ValueError("M145 completed projection requires only its typed result")
        elif (
            self.result is not None
            or self.refusal is None
            or self.effect is not OperationEffect.NONE
            or self.refusal.code not in M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION[self.operation_id]
        ):
            raise ValueError("M145 refusal must be pre-write, NONE, and carry only refusal detail")
        return self


class M145CommunicationExecutionResult(BaseModel):
    """Private encrypted operand wrapping the CLI-only terminal projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: M145CommunicationOperationResult


M145_COMMUNICATION_REQUEST_TYPES: dict[M145CommunicationOperationId, type[M145CommunicationRequest]] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: M145CommunicationCreateRequest,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: M145CommunicationValidateRequest,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: M145CommunicationExportRequest,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: M145CommunicationMarkDeliveredRequest,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: M145CommunicationMarkCompletedRequest,
}


def require_m145_communication_projection_kind(
    operation_id: M145CommunicationOperationId,
    result: M145CommunicationOutputProjection,
) -> None:
    """Reject a typed result whose discriminator does not match its command."""
    expected = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: "validation",
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: "export",
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: "record",
    }[operation_id]
    if result.kind != expected:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


__all__ = [
    "M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_OPERATION_IDS",
    "M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE",
    "M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION",
    "M145_COMMUNICATION_REFUSAL_CODE_BY_VALUE",
    "M145_COMMUNICATION_REQUEST_TYPES",
    "M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID",
    "M145CommunicationCreateRequest",
    "M145CommunicationErrorContextFact",
    "M145CommunicationExecutionResult",
    "M145CommunicationExportProjection",
    "M145CommunicationExportRequest",
    "M145CommunicationFieldValueProjection",
    "M145CommunicationMarkCompletedRequest",
    "M145CommunicationMarkDeliveredRequest",
    "M145CommunicationOperationId",
    "M145CommunicationOperationRecordNotFoundError",
    "M145CommunicationOperationResult",
    "M145CommunicationOutputProjection",
    "M145CommunicationRecordProjection",
    "M145CommunicationRefusalCode",
    "M145CommunicationRefusalProjection",
    "M145CommunicationRequest",
    "M145CommunicationValidateRequest",
    "M145CommunicationValidationIssueProjection",
    "M145CommunicationValidationProjection",
    "require_m145_communication_projection_kind",
]
