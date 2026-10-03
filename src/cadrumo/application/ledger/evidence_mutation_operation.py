"""Registered exact-profile updates and removals of purchase-invoice evidence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .evidence import (
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceResult,
    PurchaseInvoiceEvidenceService,
    PurchaseInvoiceEvidenceSnapshotConflictError,
    prepare_purchase_invoice_evidence_update,
)
from .evidence_ports import LedgerEvidencePorts, LedgerEvidencePortsFactory
from .evidence_read_operation import LedgerEvidenceRecordProjection
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID = "ledger.evidence.update"
LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID = "ledger.evidence.remove"
LEDGER_EVIDENCE_UPDATE_PHASE = LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID
LEDGER_EVIDENCE_REMOVE_PHASE = LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID

_MAX_RESULT_BYTES = 60 * 1024
_EvidenceIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_EvidenceText = Annotated[str, Field(max_length=16_384)]
_InvoiceDate = Annotated[str, Field(max_length=64)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_EvidenceEventId = Annotated[str, Field(min_length=1, max_length=64)]
_EvidenceEventIds = Annotated[tuple[_EvidenceEventId, ...], Field(min_length=1, max_length=1)]
_OptionalEvidenceEventIds = Annotated[tuple[_EvidenceEventId, ...], Field(max_length=1)]
LedgerEvidenceUpdateField = Literal[
    "supplier",
    "invoice_number",
    "invoice_date",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "notes",
]
_UpdateField = LedgerEvidenceUpdateField
_UpdateFields = Annotated[tuple[_UpdateField, ...], Field(max_length=7)]
_UPDATE_FIELDS = frozenset(
    {"supplier", "invoice_number", "invoice_date", "taxable_base", "iva_rate", "iva_amount", "notes"}
)
_DECIMAL_FIELDS = frozenset({"taxable_base", "iva_rate", "iva_amount"})


class LedgerEvidenceUpdatePatch(BaseModel):
    """Bounded wire form for the mutable evidence fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    supplier: Annotated[str, Field(max_length=1_024)] | None = None
    invoice_number: Annotated[str, Field(max_length=1_024)] | None = None
    invoice_date: _InvoiceDate | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    notes: _EvidenceText | None = None

    @field_validator("taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"{info.field_name} must use canonical non-negative decimal text")
        return value


class LedgerEvidenceUpdateRequest(BaseModel):
    """Private exact-profile update request with an explicit omission mask.

    ``patch_fields`` is authoritative because Pydantic serializes optional
    defaults as null on the private JSON wire. Matching every non-null patch
    value to that mask rejects values that would otherwise be silently ignored
    while remaining stable across the secure-reference round trip.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity
    patch: LedgerEvidenceUpdatePatch
    patch_fields: _UpdateFields = ()

    @field_validator("patch_fields")
    @classmethod
    def _unique_supported_fields(cls, value: tuple[_UpdateField, ...]) -> tuple[_UpdateField, ...]:
        if len(set(value)) != len(value) or not set(value) <= _UPDATE_FIELDS:
            raise ValueError("evidence update fields must be unique supported fields")
        return value

    @model_validator(mode="after")
    def _patch_matches_omission_mask(self) -> LedgerEvidenceUpdateRequest:
        selected = set(self.patch_fields)
        populated = {field for field in _UPDATE_FIELDS if getattr(self.patch, field) is not None}
        if selected != populated:
            raise ValueError("evidence update values must match the explicit patch field mask")
        return self


class LedgerEvidenceRemoveRequest(BaseModel):
    """Private exact-profile removal request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity


class LedgerEvidenceUpdateProjection(BaseModel):
    """Bounded successful update result for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    record: LedgerEvidenceRecordProjection
    bucket_event_ids: _OptionalEvidenceEventIds

    @model_validator(mode="after")
    def _correlate_record(self) -> LedgerEvidenceUpdateProjection:
        if self.record.bucket_id != str(self.profile_id):
            raise ValueError("evidence update result belongs to another profile")
        return self


class LedgerEvidenceRemoveProjection(BaseModel):
    """Bounded successful removal result for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    record: LedgerEvidenceRecordProjection
    bucket_event_ids: _EvidenceEventIds

    @model_validator(mode="after")
    def _correlate_record(self) -> LedgerEvidenceRemoveProjection:
        if self.record.bucket_id != str(self.profile_id):
            raise ValueError("evidence removal result belongs to another profile")
        return self


class LedgerEvidenceUpdateExecutionResult(BaseModel):
    """Private result wrapper retained in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceUpdateProjection

    @model_validator(mode="after")
    def _correlate_result(self) -> LedgerEvidenceUpdateExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence update execution result belongs to another profile")
        return self


class LedgerEvidenceRemoveExecutionResult(BaseModel):
    """Private result wrapper retained in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceRemoveProjection

    @model_validator(mode="after")
    def _correlate_result(self) -> LedgerEvidenceRemoveExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence removal execution result belongs to another profile")
        return self


@dataclass(frozen=True, slots=True)
class _PreparedUpdate:
    service: PurchaseInvoiceEvidenceService
    current: PurchaseInvoiceEvidence
    candidate: PurchaseInvoiceEvidence
    patch: PurchaseInvoiceEvidencePatch
    occurred_at: datetime
    execution_result: LedgerEvidenceUpdateExecutionResult
    changed: bool


@dataclass(frozen=True, slots=True)
class _PreparedRemove:
    service: PurchaseInvoiceEvidenceService
    current: PurchaseInvoiceEvidence
    execution_result: LedgerEvidenceRemoveExecutionResult


class LedgerEvidenceUpdateExecutor:
    """Apply one canonical evidence update in the exact active profile."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Bind the profile-scoped evidence capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceUpdateRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Preflight a bounded result, then update with a guarded effect fence."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_UPDATE_PHASE)

        def preflight() -> _PreparedUpdate:
            ports = self._ports_factory(bucket_id=bucket_id)
            _require_exact_evidence_ports(ports, bucket_id=bucket_id)
            service = PurchaseInvoiceEvidenceService(ports=ports)
            current = service.view(bucket_id=bucket_id, evidence_id=payload.evidence_id)
            _require_record_identity(current, bucket_id=bucket_id, evidence_id=payload.evidence_id)
            patch = _canonical_patch(payload.patch, payload.patch_fields)
            if not payload.patch_fields:
                projection = LedgerEvidenceUpdateProjection(
                    profile_id=payload.profile_id,
                    record=LedgerEvidenceRecordProjection.from_record(current),
                    bucket_event_ids=(),
                )
                execution_result = LedgerEvidenceUpdateExecutionResult(
                    profile_id=payload.profile_id,
                    result=projection,
                )
                _preflight_result_size(execution_result)
                return _PreparedUpdate(
                    service=service,
                    current=current,
                    candidate=current,
                    patch=patch,
                    occurred_at=now(),
                    execution_result=execution_result,
                    changed=False,
                )
            occurred_at = now()
            candidate = prepare_purchase_invoice_evidence_update(current, patch, updated_at=occurred_at)
            projection = LedgerEvidenceUpdateProjection(
                profile_id=payload.profile_id,
                record=LedgerEvidenceRecordProjection.from_record(candidate),
                bucket_event_ids=("f" * 64,),
            )
            execution_result = LedgerEvidenceUpdateExecutionResult(
                profile_id=payload.profile_id,
                result=projection,
            )
            _preflight_result_size(execution_result)
            return _PreparedUpdate(
                service=service,
                current=current,
                candidate=candidate,
                patch=patch,
                occurred_at=occurred_at,
                execution_result=execution_result,
                changed=True,
            )

        async def capture() -> str:
            prepared = await asyncio.to_thread(preflight)
            if not prepared.changed:
                await context.events.effect(OperationEffect.NONE)
                return await context.operands.put(prepared.execution_result, written_at=now())
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        prepared.service.update,
                        bucket_id=bucket_id,
                        evidence_id=payload.evidence_id,
                        patch=prepared.patch,
                        actor="cli",
                        expected_current=prepared.current,
                        occurred_at=prepared.occurred_at,
                    )
                except PurchaseInvoiceEvidenceSnapshotConflictError:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
                await context.events.effect(OperationEffect.UPDATED)
                _require_mutation_result(
                    result,
                    bucket_id=bucket_id,
                    evidence_id=payload.evidence_id,
                    expected_record=prepared.candidate,
                )
                projection = prepared.execution_result.result.model_copy(
                    update={"bucket_event_ids": result.bucket_event_ids}
                )
                execution_result = prepared.execution_result.model_copy(update={"result": projection})
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-update")


class LedgerEvidenceRemoveExecutor:
    """Apply one confirmed canonical evidence removal in the exact active profile."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Bind the profile-scoped evidence capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceRemoveRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Preflight a bounded result, then remove with a guarded effect fence."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            definition_id=LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_REMOVE_PHASE)

        def preflight() -> _PreparedRemove:
            ports = self._ports_factory(bucket_id=bucket_id)
            _require_exact_evidence_ports(ports, bucket_id=bucket_id)
            service = PurchaseInvoiceEvidenceService(ports=ports)
            current = service.view(bucket_id=bucket_id, evidence_id=payload.evidence_id)
            _require_record_identity(current, bucket_id=bucket_id, evidence_id=payload.evidence_id)
            projection = LedgerEvidenceRemoveProjection(
                profile_id=payload.profile_id,
                record=LedgerEvidenceRecordProjection.from_record(current),
                bucket_event_ids=("f" * 64,),
            )
            execution_result = LedgerEvidenceRemoveExecutionResult(
                profile_id=payload.profile_id,
                result=projection,
            )
            _preflight_result_size(execution_result)
            return _PreparedRemove(service=service, current=current, execution_result=execution_result)

        async def capture() -> str:
            prepared = await asyncio.to_thread(preflight)
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        prepared.service.remove,
                        bucket_id=bucket_id,
                        evidence_id=payload.evidence_id,
                        actor="cli",
                        expected_current=prepared.current,
                    )
                except PurchaseInvoiceEvidenceSnapshotConflictError:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
                await context.events.effect(OperationEffect.UPDATED)
                _require_mutation_result(
                    result,
                    bucket_id=bucket_id,
                    evidence_id=payload.evidence_id,
                    expected_record=prepared.current,
                )
                projection = prepared.execution_result.result.model_copy(
                    update={"bucket_event_ids": result.bucket_event_ids}
                )
                execution_result = prepared.execution_result.model_copy(update={"result": projection})
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-remove")


def _canonical_patch(
    patch: LedgerEvidenceUpdatePatch,
    patch_fields: tuple[_UpdateField, ...],
) -> PurchaseInvoiceEvidencePatch:
    """Decode stable wire strings into the canonical evidence patch model."""
    values: dict[str, object] = {}
    for field in patch_fields:
        value = getattr(patch, field)
        if field in _DECIMAL_FIELDS and value is not None:
            values[field] = Decimal(value)
        else:
            values[field] = value
    return PurchaseInvoiceEvidencePatch.model_validate(values)


def _require_worker_identity(
    *,
    request_definition_id: str,
    request_subject_ref: str,
    context: OperationExecutorContext,
    definition_id: str,
    bucket_id: str,
) -> None:
    """Refuse profile, operation, subject, and active-pointer mismatches."""
    subject = profile_operation_subject(bucket_id)
    if (
        request_definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request_subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_exact_evidence_ports(ports: LedgerEvidencePorts, *, bucket_id: str) -> None:
    """Require the evidence and event repositories to share exact-profile custody."""
    evidence_objects = getattr(ports.evidence_repository, "secure_object_repository", None)
    event_objects = getattr(ports.bucket_event_repository, "secure_object_repository", None)
    if evidence_objects is None or evidence_objects is not event_objects:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if not callable(getattr(ports.evidence_repository, "load_revisioned", None)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if not callable(getattr(ports.evidence_repository, "save_if_revision_with_secure_object_writes", None)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if not callable(getattr(ports.bucket_event_repository, "load_revisioned", None)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if bucket_id != require_active_bucket_id():
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_record_identity(record: PurchaseInvoiceEvidence, *, bucket_id: str, evidence_id: str) -> None:
    if record.bucket_id != bucket_id or record.evidence_id != evidence_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_mutation_result(
    result: PurchaseInvoiceEvidenceResult,
    *,
    bucket_id: str,
    evidence_id: str,
    expected_record: PurchaseInvoiceEvidence,
) -> None:
    _require_record_identity(result.record, bucket_id=bucket_id, evidence_id=evidence_id)
    if result.record != expected_record or len(result.bucket_event_ids) != 1:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if any(not event_id or len(event_id) > 64 for event_id in result.bucket_event_ids):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _preflight_result_size(result: BaseModel) -> None:
    """Keep the encrypted worker result comfortably below its public transport cap."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _project_terminal_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    result_type: type[BaseModel],
    profile_id: UUID,
    public_result: BaseModel,
    expected_effect: OperationEffect,
) -> BaseModel:
    """Release only a complete successful receipt for its exact profile and definition."""
    if type(result) is not result_type or receipt.identity.definition_id != definition_id:
        raise ValueError("invalid ledger evidence mutation result or operation identity")
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("ledger evidence mutation result belongs to another subject")
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not expected_effect
    ):
        raise ValueError("ledger evidence mutation has an incompatible terminal receipt")
    return public_result


def _project_update_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceUpdateExecutionResult:
        raise ValueError("invalid ledger evidence update result")
    expected_effect = OperationEffect.NONE if not result.result.bucket_event_ids else OperationEffect.UPDATED
    return _project_terminal_result(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceUpdateExecutionResult,
        profile_id=result.profile_id,
        public_result=result.result,
        expected_effect=expected_effect,
    )


def _project_remove_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceRemoveExecutionResult:
        raise ValueError("invalid ledger evidence remove result")
    return _project_terminal_result(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceRemoveExecutionResult,
        profile_id=result.profile_id,
        public_result=result.result,
        expected_effect=OperationEffect.UPDATED,
    )


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[LedgerEvidenceUpdateExecutor] | type[LedgerEvidenceRemoveExecutor],
    ports_factory: LedgerEvidencePortsFactory,
    allow_no_effect: bool = False,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=lambda: executor_type(ports_factory),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
            if allow_no_effect
            else RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_ledger_evidence_update_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare exact-profile evidence update with bounded result projection."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceUpdateRequest,
        result_type=LedgerEvidenceUpdateExecutionResult,
        executor_type=LedgerEvidenceUpdateExecutor,
        ports_factory=ports_factory,
        allow_no_effect=True,
    )


def build_ledger_evidence_remove_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare exact-profile evidence removal with bounded result projection."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceRemoveRequest,
        result_type=LedgerEvidenceRemoveExecutionResult,
        executor_type=LedgerEvidenceRemoveExecutor,
        ports_factory=ports_factory,
    )


def resolve_ledger_evidence_update_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT for evidence update."""
    if request.definition_id != LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceUpdateRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def resolve_ledger_evidence_remove_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT for evidence removal."""
    if request.definition_id != LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceRemoveRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_evidence_update_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind evidence update schemas, exact-profile access, and terminal projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceUpdateProjection,
        result_projector=_project_update_result,
        access_resolver=resolve_ledger_evidence_update_access,
    )


def build_ledger_evidence_remove_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind evidence removal schemas, exact-profile access, and terminal projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceRemoveProjection,
        result_projector=_project_remove_result,
        access_resolver=resolve_ledger_evidence_remove_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REMOVE_PHASE",
    "LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_UPDATE_PHASE",
    "LedgerEvidenceRemoveExecutionResult",
    "LedgerEvidenceRemoveExecutor",
    "LedgerEvidenceRemoveProjection",
    "LedgerEvidenceRemoveRequest",
    "LedgerEvidenceUpdateExecutionResult",
    "LedgerEvidenceUpdateExecutor",
    "LedgerEvidenceUpdateField",
    "LedgerEvidenceUpdatePatch",
    "LedgerEvidenceUpdateProjection",
    "LedgerEvidenceUpdateRequest",
    "build_ledger_evidence_remove_definition",
    "build_ledger_evidence_remove_registration",
    "build_ledger_evidence_update_definition",
    "build_ledger_evidence_update_registration",
    "resolve_ledger_evidence_remove_access",
    "resolve_ledger_evidence_update_access",
]
