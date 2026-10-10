"""Exact-profile worker reads for purchase-invoice evidence list, view and agent query.

The list and the view are a person's projections: they return the path the
operator typed when the evidence was added. The query serves the same records
to an agent and names the file without the directory it came from.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import (
    OperationFailureErrorCode,
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
    terminal_receipt_matches,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence import MediaKind, PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from .evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from .evidence_ports import LedgerEvidencePortsFactory
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.list"
LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.view"
LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID = "ledger.evidence.query"
LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE = "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"
_MAX_EVIDENCE_LIST_ROWS = 4_096
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_EvidenceIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_SourcePath = Annotated[str, Field(min_length=1, max_length=4_096)]
_SourceFileName = Annotated[str, Field(min_length=1, max_length=4_096)]
_Supplier = Annotated[str, Field(max_length=1_024)]
_InvoiceNumber = Annotated[str, Field(max_length=1_024)]
_InvoiceDate = Annotated[str, Field(max_length=64)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_Notes = Annotated[str, Field(max_length=16_384)]


class LedgerEvidenceListRequest(BaseModel):
    """Private request for one profile's complete purchase-evidence list."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerEvidenceViewRequest(BaseModel):
    """Private exact-profile request for one evidence identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity


class LedgerEvidenceQueryRequest(BaseModel):
    """Private request for one profile's evidence records, or the one with an exact identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity | None = None


class LedgerEvidenceRecordProjection(BaseModel):
    """Bounded allowlist of fields already shown by the evidence CLI."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_id: _EvidenceIdentity
    bucket_id: BucketId
    source_path: _SourcePath
    source_sha256: ContentDigest
    attachment_id: Hex64Str
    media_kind: MediaKind
    supplier: _Supplier | None = None
    invoice_number: _InvoiceNumber | None = None
    invoice_date: _InvoiceDate | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    notes: _Notes = ""
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    @pydantic_validation_boundary
    def _timestamps_are_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_record(cls, record: PurchaseInvoiceEvidence) -> LedgerEvidenceRecordProjection:
        """Copy the canonical record through this bounded public allowlist."""
        decimal_values = tuple(
            None if value is None else str(value) for value in (record.taxable_base, record.iva_rate, record.iva_amount)
        )
        bounded_values = (
            (record.source_path, 4_096),
            (record.supplier, 1_024),
            (record.invoice_number, 1_024),
            (record.invoice_date, 64),
            (decimal_values[0], 128),
            (decimal_values[1], 128),
            (decimal_values[2], 128),
            (record.notes, 16_384),
        )
        if any(value is not None and len(value) > maximum for value, maximum in bounded_values):
            # Persisted evidence metadata predates this bounded worker result.
            # Refuse the whole read instead of truncating a canonical field or
            # letting a validation error settle as an opaque failed operation.
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        try:
            validate_utc_aware(record.created_at)
            validate_utc_aware(record.updated_at)
        except CoreValidationError:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
        return cls(
            evidence_id=record.evidence_id,
            bucket_id=record.bucket_id,
            source_path=record.source_path,
            source_sha256=record.source_sha256,
            attachment_id=record.attachment_id,
            media_kind=record.media_kind,
            supplier=record.supplier,
            invoice_number=record.invoice_number,
            invoice_date=record.invoice_date,
            taxable_base=decimal_values[0],
            iva_rate=decimal_values[1],
            iva_amount=decimal_values[2],
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def _source_file_name(source_path: str) -> str | None:
    """Return the last component of the typed path, on either path convention."""
    # The path was typed on whichever machine added the evidence. The Windows
    # reading splits on both separators, so it finds the name in either form.
    return PureWindowsPath(source_path).name or None


class LedgerEvidenceAgentRecordProjection(BaseModel):
    """One evidence record as an agent receives it: every field but the directory it was added from."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_id: _EvidenceIdentity
    bucket_id: BucketId
    source_file_name: _SourceFileName | None = None
    source_sha256: ContentDigest
    attachment_id: Hex64Str
    media_kind: MediaKind
    supplier: _Supplier | None = None
    invoice_number: _InvoiceNumber | None = None
    invoice_date: _InvoiceDate | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    notes: _Notes = ""
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    @pydantic_validation_boundary
    def _timestamps_are_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_person_projection(cls, record: LedgerEvidenceRecordProjection) -> LedgerEvidenceAgentRecordProjection:
        """Copy the person's bounded record, keeping the file name and dropping where it lay."""
        return cls(
            evidence_id=record.evidence_id,
            bucket_id=record.bucket_id,
            source_file_name=_source_file_name(record.source_path),
            source_sha256=record.source_sha256,
            attachment_id=record.attachment_id,
            media_kind=record.media_kind,
            supplier=record.supplier,
            invoice_number=record.invoice_number,
            invoice_date=record.invoice_date,
            taxable_base=record.taxable_base,
            iva_rate=record.iva_rate,
            iva_amount=record.iva_amount,
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


_EvidenceRows = Annotated[tuple[LedgerEvidenceRecordProjection, ...], Field(max_length=_MAX_EVIDENCE_LIST_ROWS)]
_EvidenceAgentRows = Annotated[
    tuple[LedgerEvidenceAgentRecordProjection, ...], Field(max_length=_MAX_EVIDENCE_LIST_ROWS)
]


class LedgerEvidenceListProjection(BaseModel):
    """Complete bounded evidence list for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    count: NonNegativeInt
    rows: _EvidenceRows

    @model_validator(mode="after")
    def _correlate_profile_and_rows(self) -> LedgerEvidenceListProjection:
        if self.count != len(self.rows):
            raise ValueError("evidence list count does not match its rows")
        profile_id = str(self.profile_id)
        if any(row.bucket_id != profile_id for row in self.rows):
            raise ValueError("evidence list contains a record from another profile")
        if len({row.evidence_id for row in self.rows}) != len(self.rows):
            raise ValueError("evidence list repeats an identity")
        return self


class LedgerEvidenceQueryProjection(BaseModel):
    """The profile's evidence records for an agent, complete or narrowed to one identity.

    An identity that names no record leaves ``rows`` empty, so the count says
    whether the record exists.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity | None = None
    count: NonNegativeInt
    rows: _EvidenceAgentRows

    @model_validator(mode="after")
    def _correlate_profile_and_rows(self) -> LedgerEvidenceQueryProjection:
        if self.count != len(self.rows):
            raise ValueError("evidence query count does not match its rows")
        profile_id = str(self.profile_id)
        if any(row.bucket_id != profile_id for row in self.rows):
            raise ValueError("evidence query contains a record from another profile")
        if len({row.evidence_id for row in self.rows}) != len(self.rows):
            raise ValueError("evidence query repeats an identity")
        if self.evidence_id is not None and any(row.evidence_id != self.evidence_id for row in self.rows):
            raise ValueError("evidence query contains a record other than the one asked for")
        return self


class LedgerEvidenceViewSuccess(BaseModel):
    """The existing bounded evidence record returned by a successful read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["success"] = "success"
    record: LedgerEvidenceRecordProjection


class LedgerEvidenceViewRefusal(BaseModel):
    """Only the static missing-reference fact crosses the refusal detail door."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["refused"] = "refused"
    evidence_record_present: Literal[False] = False


class LedgerEvidenceViewProjection(BaseModel):
    """Versioned exact-profile success or finite missing-reference refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[2] = 2
    profile_id: UUID
    outcome: Annotated[LedgerEvidenceViewSuccess | LedgerEvidenceViewRefusal, Field(discriminator="kind")]

    @model_validator(mode="after")
    def _correlate_record_profile(self) -> LedgerEvidenceViewProjection:
        if isinstance(self.outcome, LedgerEvidenceViewSuccess) and self.outcome.record.bucket_id != str(
            self.profile_id
        ):
            raise ValueError("evidence view record belongs to another profile")
        return self


class LedgerEvidenceListExecutionResult(BaseModel):
    """Private encrypted result wrapper carrying the projection's exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceListProjection

    @model_validator(mode="after")
    def _correlate_result_profile(self) -> LedgerEvidenceListExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence list execution result belongs to another profile")
        return self


class LedgerEvidenceViewExecutionResult(BaseModel):
    """Private encrypted result wrapper carrying the projection's exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceViewProjection

    @model_validator(mode="after")
    def _correlate_result_profile(self) -> LedgerEvidenceViewExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence view execution result belongs to another profile")
        return self


class LedgerEvidenceQueryExecutionResult(BaseModel):
    """Private encrypted result wrapper carrying the projection's exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceQueryProjection

    @model_validator(mode="after")
    def _correlate_result_profile(self) -> LedgerEvidenceQueryExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence query execution result belongs to another profile")
        return self


def _require_terminal_success(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
) -> None:
    """Bind a public read result to a complete successful operation receipt."""
    _require_read_receipt(receipt, definition_id=definition_id, profile_id=profile_id)
    if getattr(result, "profile_id", None) != profile_id:
        raise ValueError("evidence read result belongs to another profile")


def _require_read_receipt(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
) -> None:
    """Require the terminal receipt identity and effect for a successful read."""
    message = "evidence read result has an incompatible terminal receipt"
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.NONE,
        message=message,
    )


def _project_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the exact list result carried by its successful receipt."""
    if type(result) is not LedgerEvidenceListExecutionResult:
        raise ValueError("invalid ledger evidence list result")
    _require_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
    )
    return result.result


def _project_view_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the closed outcome matching its exact terminal receipt."""
    if type(result) is not LedgerEvidenceViewExecutionResult:
        raise ValueError("invalid ledger evidence view result")
    private = LedgerEvidenceViewExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if isinstance(private.result.outcome, LedgerEvidenceViewRefusal):
        if (
            not terminal_receipt_matches(
                receipt,
                definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(private.profile_id)),
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.NONE,
            )
            or receipt.refusal_ref != LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
        ):
            raise ValueError("evidence view refusal has an incompatible terminal receipt")
    else:
        _require_terminal_success(
            private,
            receipt,
            definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
            profile_id=private.profile_id,
        )
    return private.result


def _project_query_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the exact query result carried by its successful receipt."""
    if type(result) is not LedgerEvidenceQueryExecutionResult:
        raise ValueError("invalid ledger evidence query result")
    _require_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
    )
    return result.result


def _check_result_size(result: BaseModel) -> None:
    """Refuse a public read result that cannot fit the bounded projection document."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


class LedgerEvidenceReadExecutor:
    """Read only canonical evidence metadata in the worker's active profile."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Retain the runtime composition's bucket-scoped evidence capability."""
        self._ports_factory = ports_factory

    async def execute_list(
        self,
        request: OperationRequest[LedgerEvidenceListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture the complete list as an encrypted, no-effect worker result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceListProjection:
            rows = self._bounded_rows(bucket_id)
            result = LedgerEvidenceListProjection(profile_id=payload.profile_id, count=len(rows), rows=rows)
            _check_result_size(result)
            return result

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            execution_result = LedgerEvidenceListExecutionResult(profile_id=payload.profile_id, result=result)
            reference = await context.operands.put(execution_result, written_at=now())
            return reference

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-list")

    def _bounded_rows(self, bucket_id: str) -> tuple[LedgerEvidenceRecordProjection, ...]:
        """Read every record of the profile through the bounded allowlist, or refuse the whole read."""
        ports = self._ports_factory(bucket_id=bucket_id)
        records = PurchaseInvoiceEvidenceService(ports=ports).list_all(bucket_id=bucket_id)
        identities = {record.evidence_id for record in records}
        if (
            len(records) > _MAX_EVIDENCE_LIST_ROWS
            or any(record.bucket_id != bucket_id for record in records)
            or len(identities) != len(records)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return tuple(LedgerEvidenceRecordProjection.from_record(record) for record in records)

    async def execute_query(
        self,
        request: OperationRequest[LedgerEvidenceQueryRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture the agent's reduced records as an encrypted, no-effect worker result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            definition_id=LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceQueryProjection:
            # The person's bounded rows are built once and stay in worker
            # memory; only the reduced rows enter the result operand.
            rows = tuple(
                LedgerEvidenceAgentRecordProjection.from_person_projection(row)
                for row in self._bounded_rows(bucket_id)
                if payload.evidence_id is None or row.evidence_id == payload.evidence_id
            )
            result = LedgerEvidenceQueryProjection(
                profile_id=payload.profile_id, evidence_id=payload.evidence_id, count=len(rows), rows=rows
            )
            _check_result_size(result)
            return result

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            execution_result = LedgerEvidenceQueryExecutionResult(profile_id=payload.profile_id, result=result)
            return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-query")

    async def execute_view(
        self,
        request: OperationRequest[LedgerEvidenceViewRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Capture a record or the finite missing-reference fact in encrypted custody."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceViewProjection:
            ports = self._ports_factory(bucket_id=bucket_id)
            try:
                record = PurchaseInvoiceEvidenceService(ports=ports).view(
                    bucket_id=bucket_id,
                    evidence_id=payload.evidence_id,
                )
            except PurchaseInvoiceEvidenceNotFoundError:
                # Never copy exception context, request identifiers or metadata.
                return LedgerEvidenceViewProjection(profile_id=payload.profile_id, outcome=LedgerEvidenceViewRefusal())
            if record.bucket_id != bucket_id or record.evidence_id != payload.evidence_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            result = LedgerEvidenceViewProjection(
                profile_id=payload.profile_id,
                outcome=LedgerEvidenceViewSuccess(record=LedgerEvidenceRecordProjection.from_record(record)),
            )
            _check_result_size(result)
            return result

        async def capture() -> str | OperationRefusalEvidence:
            result = await asyncio.to_thread(read)
            execution_result = LedgerEvidenceViewExecutionResult(profile_id=payload.profile_id, result=result)
            reference = await context.operands.put(execution_result, written_at=now())
            if isinstance(result.outcome, LedgerEvidenceViewRefusal):
                return OperationRefusalEvidence(
                    refusal_code=LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
                    detail_ref=reference,
                )
            return reference

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-view")


def _require_worker_identity(
    *,
    request_definition_id: str,
    request_subject_ref: str,
    context: OperationExecutorContext,
    definition_id: str,
    bucket_id: str,
) -> None:
    """Refuse a profile, definition, or active-pointer mismatch before reading."""
    subject = profile_operation_subject(bucket_id)
    if (
        request_definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request_subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class LedgerEvidenceListExecutor:
    """Bind list requests to the shared read executor."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Compose the shared evidence read service."""
        self._reader = LedgerEvidenceReadExecutor(ports_factory)

    async def execute(
        self, request: OperationRequest[LedgerEvidenceListRequest], context: OperationExecutorContext
    ) -> str:
        """Run the exact-profile list read."""
        return await self._reader.execute_list(request, context)


class LedgerEvidenceViewExecutor:
    """Bind view requests to the shared read executor."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Compose the shared evidence read service."""
        self._reader = LedgerEvidenceReadExecutor(ports_factory)

    async def execute(
        self, request: OperationRequest[LedgerEvidenceViewRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Run the exact-profile view read."""
        return await self._reader.execute_view(request, context)


class LedgerEvidenceQueryExecutor:
    """Bind agent query requests to the shared read executor."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Compose the shared evidence read service."""
        self._reader = LedgerEvidenceReadExecutor(ports_factory)

    async def execute(
        self, request: OperationRequest[LedgerEvidenceQueryRequest], context: OperationExecutorContext
    ) -> str:
        """Run the exact-profile agent query."""
        return await self._reader.execute_query(request, context)


_PERSON_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_AGENT_FRONTENDS = frozenset({OperationFrontendProjection.MCP})


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[LedgerEvidenceListExecutor]
    | type[LedgerEvidenceViewExecutor]
    | type[LedgerEvidenceQueryExecutor],
    ports_factory: LedgerEvidencePortsFactory,
    permitted_frontends: frozenset[OperationFrontendProjection] = _PERSON_FRONTENDS,
    refusal_detail_codes: frozenset[OperationFailureErrorCode] = frozenset(),
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_type,
        executor_type=executor_type,
        build=lambda: executor_type(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=permitted_frontends,
        refusal_detail_codes=refusal_detail_codes,
    )


def build_ledger_evidence_list_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare a bounded exact-profile purchase-evidence list read."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceListRequest,
        result_type=LedgerEvidenceListExecutionResult,
        executor_type=LedgerEvidenceListExecutor,
        ports_factory=ports_factory,
    )


def build_ledger_evidence_view_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare a bounded exact-profile purchase-evidence view read."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceViewRequest,
        result_type=LedgerEvidenceViewExecutionResult,
        executor_type=LedgerEvidenceViewExecutor,
        ports_factory=ports_factory,
        refusal_detail_codes=frozenset({LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE}),
    )


def build_ledger_evidence_query_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare the agent-only evidence read that serves the list and the view."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceQueryRequest,
        result_type=LedgerEvidenceQueryExecutionResult,
        executor_type=LedgerEvidenceQueryExecutor,
        ports_factory=ports_factory,
        permitted_frontends=_AGENT_FRONTENDS,
    )


def _resolve_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if request.definition_id != LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceListRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )


def _resolve_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if request.definition_id != LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceViewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )


def _resolve_query_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if context.frontend is not OperationFrontendProjection.MCP:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if request.definition_id != LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceQueryRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )


def build_ledger_evidence_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the exact list request/result contracts and whole-profile disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceListProjection,
        result_projector=_project_list_result,
        access_resolver=_resolve_list_access,
    )


def build_ledger_evidence_view_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the exact view request/result contracts and whole-profile disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=definition.request_type
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=2, model_type=LedgerEvidenceViewProjection
        ),
        result_projector=_project_view_result,
        access_resolver=_resolve_view_access,
    )


def build_ledger_evidence_query_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the agent query's request/result contracts and whole-profile disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceQueryProjection,
        result_projector=_project_query_result,
        access_resolver=_resolve_query_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE",
    "LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID",
    "LedgerEvidenceAgentRecordProjection",
    "LedgerEvidenceListExecutionResult",
    "LedgerEvidenceListExecutor",
    "LedgerEvidenceListProjection",
    "LedgerEvidenceListRequest",
    "LedgerEvidenceQueryExecutionResult",
    "LedgerEvidenceQueryExecutor",
    "LedgerEvidenceQueryProjection",
    "LedgerEvidenceQueryRequest",
    "LedgerEvidenceRecordProjection",
    "LedgerEvidenceViewExecutionResult",
    "LedgerEvidenceViewExecutor",
    "LedgerEvidenceViewProjection",
    "LedgerEvidenceViewRefusal",
    "LedgerEvidenceViewRequest",
    "LedgerEvidenceViewSuccess",
    "build_ledger_evidence_list_definition",
    "build_ledger_evidence_list_registration",
    "build_ledger_evidence_query_definition",
    "build_ledger_evidence_query_registration",
    "build_ledger_evidence_view_definition",
    "build_ledger_evidence_view_registration",
]
