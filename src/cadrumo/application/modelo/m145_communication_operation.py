"""Exact-profile registered operations for the local Modelo 145 workflow.

The canonical record service remains the sole owner of validation, rendering,
state transitions, and history payloads. This module adds encrypted request and
result custody, exact-profile admission, and a gate at the service's actual
repository mutation calls. Exported bytes stay in the encrypted operation
result until the local CLI reads them; only their receipt is written to bucket
history.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Annotated, Literal, Protocol, override, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_id import CasillaId
from ...core.errors.error_codes import scrub_error_context
from ...core.hashing import sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventHistoryCatalogue
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.fixed_width_codec import ExportEncoding
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ._ports import FicheroBoeRecordRenderer
from .m145_communication_period import M145CommunicationPeriod
from .m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordState,
    M145CommunicationRecordTransitionError,
    M145CommunicationRecordValidationError,
    M145CommunicationServiceError,
    M145CommunicationValidationIssue,
    M145CommunicationValidationIssueKind,
    M145CommunicationValidationResult,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    validate_m145_communication_record,
)
from .m145_communication_records_ports import (
    M145CommunicationRecordRepositoryPort,
    M145CommunicationRecordsPorts,
    M145CommunicationRecordsPortsFactory,
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

_OPERATION_IDS: tuple[M145CommunicationOperationId, ...] = (
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
_M145_REFUSAL_CODES: dict[M145CommunicationOperationId, frozenset[M145CommunicationRefusalCode]] = {
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
_M145_REFUSAL_CODE_BY_VALUE: dict[str, M145CommunicationRefusalCode] = {
    code: code for codes in _M145_REFUSAL_CODES.values() for code in codes
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
            or self.refusal.code not in _M145_REFUSAL_CODES[self.operation_id]
        ):
            raise ValueError("M145 refusal must be pre-write, NONE, and carry only refusal detail")
        return self


class M145CommunicationExecutionResult(BaseModel):
    """Private encrypted operand wrapping the CLI-only terminal projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: M145CommunicationOperationResult


def project_m145_communication_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the encrypted terminal detail only with its exact settled receipt."""
    if type(result) is not M145CommunicationExecutionResult:
        raise ValueError("invalid M145 private result type")
    projected = result.result
    if (
        receipt.identity.definition_id != projected.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projected.profile_id))
        or receipt.effect is not projected.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("M145 result differs from its terminal receipt")
    if projected.outcome == "completed":
        if projected.result is None:
            raise ValueError("M145 success has no typed result")
        _require_projection_kind(projected.operation_id, projected.result)
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
        ):
            raise ValueError("M145 success has an incompatible terminal receipt")
    elif (
        projected.refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.result_ref is not None
        or receipt.refusal_detail_ref is None
        or receipt.refusal_ref != projected.refusal.code
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("M145 refusal has an incompatible terminal receipt")
    return projected


class _WriteGate:
    """Bridge a synchronous canonical repository call to the async effect fence."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.requested = asyncio.Event()
        self.finished = asyncio.Event()
        self._released = threading.Event()
        self._allowed = False
        self.started = False
        self.succeeded = False

    def enter[T](self, commit: Callable[[], T]) -> T:
        """Wait for the worker to publish UNKNOWN, then execute the repository call."""
        self.started = True
        self._loop.call_soon_threadsafe(self.requested.set)
        self._released.wait()
        if not self._allowed:
            self._loop.call_soon_threadsafe(self.finished.set)
            raise RuntimeError("M145 repository mutation was not admitted by its operation fence")
        try:
            result = commit()
        except BaseException:
            self._loop.call_soon_threadsafe(self.finished.set)
            raise
        self.succeeded = True
        self._loop.call_soon_threadsafe(self.finished.set)
        return result

    def allow(self) -> None:
        self._allowed = True
        self._released.set()

    def deny(self) -> None:
        self._released.set()

    @property
    def released(self) -> bool:
        return self._released.is_set()


class _TrackedM145RecordRepository(M145CommunicationRecordRepositoryPort):
    """Observe only the record/event atomic save; leave reads and write prep outside."""

    def __init__(self, repository: M145CommunicationRecordRepositoryPort, gate: _WriteGate) -> None:
        self._repository = repository
        self._gate = gate

    @override
    def exists(self, communication_record_id: str) -> bool:
        return self._repository.exists(communication_record_id)

    @override
    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        return self._repository.load(communication_record_id)

    @override
    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        return self._repository.resolve(communication_record_id)

    @override
    def save_with_secure_object_writes(
        self,
        record: M145CommunicationRecord,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self._gate.enter(lambda: self._repository.save_with_secure_object_writes(record, extra_writes))


@runtime_checkable
class _RevisionGuardedM145EventAppender(Protocol):
    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue: ...


class _TrackedM145EventRepository(BucketEventHistoryRepositoryProtocol):
    """Fence the standalone export receipt append after canonical rendering."""

    def __init__(self, repository: BucketEventHistoryRepositoryProtocol, gate: _WriteGate) -> None:
        self._repository = repository
        self._gate = gate

    @override
    def exists(self) -> bool:
        return self._repository.exists()

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._repository.load()

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._gate.enter(lambda: self._repository.save(catalogue))

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        repository = self._repository
        if not isinstance(repository, _RevisionGuardedM145EventAppender):
            raise RuntimeError("M145 export requires a revision-guarded event-history repository")
        return self._gate.enter(lambda: repository.append_guarded(appender, attempts=attempts))

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return self._repository.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


class M145CommunicationExecutor:
    """Delegate one command to the canonical M145 service under exact-profile authority."""

    def __init__(
        self,
        *,
        records_ports_factory: M145CommunicationRecordsPortsFactory,
        renderer_factory: Callable[[], FicheroBoeRecordRenderer],
    ) -> None:
        self._records_ports_factory = records_ports_factory
        self._renderer_factory = renderer_factory

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        operation_id = request.definition_id
        if (
            operation_id not in _OPERATION_IDS
            or context.identity.definition_id != operation_id
            or context.identity.subject_ref != request.subject_ref
            or not isinstance(
                payload,
                (
                    M145CommunicationCreateRequest,
                    M145CommunicationValidateRequest,
                    M145CommunicationExportRequest,
                    M145CommunicationMarkDeliveredRequest,
                    M145CommunicationMarkCompletedRequest,
                ),
            )
            or not isinstance(payload, _REQUEST_TYPES[operation_id])
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.subject_ref != profile_operation_subject(str(payload.profile_id)):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        bucket_id = str(payload.profile_id)
        if await asyncio.to_thread(require_active_bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        operation = context.authority_operation
        await context.events.phase(operation_id)
        ports = await asyncio.to_thread(self._records_ports_factory, bucket_id=bucket_id)

        async def run() -> str | OperationRefusalEvidence:
            gate = _WriteGate(asyncio.get_running_loop())
            tracked_ports = self._tracked_ports(ports, operation_id=operation_id, gate=gate)
            service_task = asyncio.create_task(
                asyncio.to_thread(
                    self._invoke,
                    payload=payload,
                    operation_id=operation_id,
                    bucket_id=bucket_id,
                    ports=tracked_ports,
                    authority=operation,
                ),
                name=f"{operation_id}-canonical-service",
            )
            request_task = asyncio.create_task(gate.requested.wait(), name=f"{operation_id}-write-request")
            try:
                completed, _ = await asyncio.wait(
                    (service_task, request_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if service_task in completed:
                    request_task.cancel()
                    try:
                        value = await service_task
                    except _CANONICAL_REFUSAL_TYPES as error:
                        if gate.started:
                            raise
                        return await self._publish_refusal(
                            context,
                            profile_id=payload.profile_id,
                            operation_id=operation_id,
                            error=error,
                        )
                    except BaseException:
                        if not gate.started:
                            await context.events.effect(OperationEffect.NONE)
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return await self._publish_success(
                        context,
                        profile_id=payload.profile_id,
                        operation_id=operation_id,
                        value=value,
                        effect=OperationEffect.NONE,
                    )

                async with context.cancellation.irreversible_section():
                    await context.events.effect(OperationEffect.UNKNOWN)
                    gate.allow()
                    await gate.finished.wait()
                    if gate.succeeded:
                        await context.events.effect(OperationEffect.UPDATED)
                    value = await service_task
                    effect = OperationEffect.UPDATED if gate.succeeded else OperationEffect.UNKNOWN
                return await self._publish_success(
                    context,
                    profile_id=payload.profile_id,
                    operation_id=operation_id,
                    value=value,
                    effect=effect,
                )
            finally:
                if not gate.released:
                    gate.deny()
                if not request_task.done():
                    request_task.cancel()
                if not service_task.done():
                    await asyncio.gather(service_task, return_exceptions=True)

        return await await_cancellation_complete(run(), task_name=operation_id)

    def _tracked_ports(
        self,
        ports: M145CommunicationRecordsPorts,
        *,
        operation_id: M145CommunicationOperationId,
        gate: _WriteGate,
    ) -> M145CommunicationRecordsPorts:
        if operation_id == M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID:
            return replace(
                ports, bucket_event_repository=_TrackedM145EventRepository(ports.bucket_event_repository, gate)
            )
        if operation_id in {
            M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
            M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
            M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
        }:
            return replace(ports, record_repository=_TrackedM145RecordRepository(ports.record_repository, gate))
        return ports

    def _invoke(
        self,
        *,
        payload: BaseModel,
        operation_id: M145CommunicationOperationId,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult:
        if (
            isinstance(payload, M145CommunicationCreateRequest)
            and operation_id == M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID
        ):
            return create_m145_communication_record(
                payload.to_command(),
                bucket_id=bucket_id,
                ports=ports,
                operation=authority,
                actor=payload.actor,
            )
        if (
            isinstance(payload, M145CommunicationValidateRequest)
            and operation_id == M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
        ):
            return validate_m145_communication_record(
                payload.communication_record_id,
                bucket_id=bucket_id,
                ports=ports,
                operation=authority,
            )
        if (
            isinstance(payload, M145CommunicationExportRequest)
            and operation_id == M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID
        ):
            return export_m145_communication_record(
                payload.communication_record_id,
                bucket_id=bucket_id,
                renderer=self._renderer_factory(),
                ports=ports,
                operation=authority,
                actor=payload.actor,
            )
        if (
            isinstance(payload, M145CommunicationMarkDeliveredRequest)
            and operation_id == M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID
        ):
            return mark_m145_communication_record_delivered_to_payer(
                payload.communication_record_id,
                bucket_id=bucket_id,
                ports=ports,
                operation=authority,
                actor=payload.actor,
            )
        if (
            isinstance(payload, M145CommunicationMarkCompletedRequest)
            and operation_id == M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID
        ):
            return mark_m145_communication_record_locally_completed(
                payload.communication_record_id,
                bucket_id=bucket_id,
                ports=ports,
                operation=authority,
                actor=payload.actor,
            )
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    async def _publish_success(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: M145CommunicationOperationId,
        value: M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult,
        effect: OperationEffect,
    ) -> str:
        if isinstance(value, M145CommunicationRecord):
            projected: M145CommunicationOutputProjection = M145CommunicationRecordProjection.from_record(value)
        elif isinstance(value, M145CommunicationValidationResult):
            projected = M145CommunicationValidationProjection.from_result(value)
        else:
            projected = M145CommunicationExportProjection.from_result(value)
        _require_projection_kind(operation_id, projected)
        result = M145CommunicationOperationResult(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="completed",
            effect=effect,
            result=projected,
        )
        detail = M145CommunicationExecutionResult(result=result)
        reference = await context.operands.put(detail, written_at=now())
        return reference

    async def _publish_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: M145CommunicationOperationId,
        error: M145CommunicationServiceError,
    ) -> OperationRefusalEvidence:
        if isinstance(error, M145CommunicationRecordNotFoundError):
            operation_error = M145CommunicationOperationRecordNotFoundError(
                str(error),
                context=error.context,
            )
            refusal_code = M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE
        else:
            operation_error = error
            refusal_code = error.code.code
        typed_refusal_code = _M145_REFUSAL_CODE_BY_VALUE.get(refusal_code)
        if typed_refusal_code is None or typed_refusal_code not in _M145_REFUSAL_CODES[operation_id]:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        safe_context = scrub_error_context(operation_error.context) or {}
        refusal = M145CommunicationRefusalProjection(
            code=typed_refusal_code,
            message=str(operation_error) or operation_error.translated_message or operation_error.code.message_key,
            context=tuple(
                M145CommunicationErrorContextFact(key=key, value=value) for key, value in safe_context.items()
            ),
        )
        result = M145CommunicationOperationResult(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="prewrite_refusal",
            effect=OperationEffect.NONE,
            refusal=refusal,
        )
        reference = await context.operands.put(M145CommunicationExecutionResult(result=result), written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=refusal_code, detail_ref=reference)


_CANONICAL_REFUSAL_TYPES = (
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordValidationError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordTransitionError,
)

_REQUEST_TYPES: dict[M145CommunicationOperationId, type[BaseModel]] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: M145CommunicationCreateRequest,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: M145CommunicationValidateRequest,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: M145CommunicationExportRequest,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: M145CommunicationMarkDeliveredRequest,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: M145CommunicationMarkCompletedRequest,
}


def _require_projection_kind(
    operation_id: M145CommunicationOperationId,
    result: M145CommunicationOutputProjection,
) -> None:
    expected = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: "validation",
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: "export",
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: "record",
    }[operation_id]
    if result.kind != expected:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _resolve_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    operation_id: M145CommunicationOperationId,
    request_type: type[BaseModel],
    permission: AccessAction,
) -> ResolvedOperationAccess:
    payload = request.payload
    if request.definition_id != operation_id or not isinstance(payload, request_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = getattr(payload, "profile_id", None)
    subject = profile_operation_subject(str(profile_id)) if isinstance(profile_id, UUID) else None
    if profile_id != context.profile_id or request.subject_ref != subject:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    admitted = context.admitted_request
    if (
        admitted is not None
        and context.action
        in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }
        and (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != operation_id
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods
            or not admitted.period_independent
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = frozenset[DisclosurePermission]()
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id="operation.observation",
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            ),
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            ),
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=operation_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=operation_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    permission,
                },
            ),
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def _build_definition(
    *,
    operation_id: M145CommunicationOperationId,
    request_type: type[BaseModel],
    records_ports_factory: M145CommunicationRecordsPortsFactory,
    renderer_factory: Callable[[], FicheroBoeRecordRenderer],
) -> OperationDefinition:
    mutating = operation_id != M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
    return OperationDefinition(
        definition_id=operation_id,
        request_type=request_type,
        result_type=M145CommunicationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=M145CommunicationExecutor,
            build=lambda: M145CommunicationExecutor(
                records_ports_factory=records_ports_factory,
                renderer_factory=renderer_factory,
            ),
        ),
        phase_codes=(operation_id,),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                if mutating
                else {OperationEffect.NONE, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=_M145_REFUSAL_CODES[operation_id],
    )


def build_m145_communication_operation_definitions(
    *,
    records_ports_factory: M145CommunicationRecordsPortsFactory,
    renderer_factory: Callable[[], FicheroBoeRecordRenderer],
) -> tuple[OperationDefinition, ...]:
    """Build all five existing CLI identities over the canonical record service."""
    return tuple(
        sorted(
            (
                _build_definition(
                    operation_id=operation_id,
                    request_type=request_type,
                    records_ports_factory=records_ports_factory,
                    renderer_factory=renderer_factory,
                )
                for operation_id, request_type in _REQUEST_TYPES.items()
            ),
            key=lambda definition: definition.definition_id,
        ),
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    permission: AccessAction,
) -> OperationPublicDefinitionRegistrationV1:
    operation_id = definition.definition_id
    if operation_id not in _OPERATION_IDS:
        raise ValueError("M145 registration received an unknown operation definition")

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return _resolve_access(
            request,
            context,
            operation_id=operation_id,
            request_type=request_type,
            permission=permission,
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=operation_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=operation_id + ".result",
            schema_version=1,
            model_type=M145CommunicationOperationResult,
        ),
        result_projector=project_m145_communication_result,
        access_resolver=resolve,
    )


def build_m145_communication_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Register strict schemas and exact-profile all-period access for each command."""
    permissions: dict[M145CommunicationOperationId, AccessAction] = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: AccessAction.SUBMIT,
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
    }
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        operation_id = definition.definition_id
        if operation_id not in _REQUEST_TYPES:
            raise ValueError("M145 registration population contains an unknown operation")
        typed_id = operation_id  # narrowed by membership above
        registrations.append(
            _registration(
                definition,
                request_type=_REQUEST_TYPES[typed_id],
                permission=permissions[typed_id],
            ),
        )
    return tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id))


__all__ = [
    "M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID",
    "M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE",
    "M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID",
    "M145CommunicationCreateRequest",
    "M145CommunicationErrorContextFact",
    "M145CommunicationExecutionResult",
    "M145CommunicationExportProjection",
    "M145CommunicationExportRequest",
    "M145CommunicationFieldValueProjection",
    "M145CommunicationMarkCompletedRequest",
    "M145CommunicationMarkDeliveredRequest",
    "M145CommunicationOperationRecordNotFoundError",
    "M145CommunicationOperationResult",
    "M145CommunicationRecordProjection",
    "M145CommunicationRefusalProjection",
    "M145CommunicationValidateRequest",
    "M145CommunicationValidationIssueProjection",
    "M145CommunicationValidationProjection",
    "build_m145_communication_operation_definitions",
    "build_m145_communication_operation_registrations",
]
