"""Registered exact-profile creation of purchase-invoice evidence."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
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
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceResult,
    PurchaseInvoiceEvidenceService,
    derive_keyed_purchase_invoice_evidence_id,
)
from .evidence_ports import (
    LedgerEvidencePorts,
    LedgerEvidencePortsFactory,
    ProfileBoundEvidenceAttachmentIngestorProtocol,
    RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol,
)
from .evidence_read_operation import LedgerEvidenceRecordProjection
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID = "ledger.evidence.add"
LEDGER_EVIDENCE_ADD_PHASE = LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID

_MAX_RESULT_BYTES = 60 * 1024
_EvidenceText = Annotated[str, Field(max_length=16_384)]
_EvidencePath = Annotated[str, Field(min_length=1, max_length=4_096)]
_EvidenceLabel = Annotated[str, Field(max_length=1_024)]
_InvoiceDate = Annotated[str, Field(min_length=10, max_length=10)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_IdempotencyKey = Annotated[str, Field(max_length=256)]
_EvidenceEventId = Annotated[str, Field(min_length=1, max_length=64)]
_EvidenceEventIds = Annotated[tuple[_EvidenceEventId, ...], Field(max_length=1)]


class LedgerEvidenceAddRequest(BaseModel):
    """Bounded private request using stable string wire forms for private values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    source_path: _EvidencePath
    supplier: _EvidenceLabel | None = None
    invoice_number: _EvidenceLabel | None = None
    invoice_date: _InvoiceDate | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    notes: _EvidenceText = ""
    idempotency_key: _IdempotencyKey | None = None

    @field_validator("invoice_date")
    @classmethod
    def _iso_invoice_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("invoice_date must use YYYY-MM-DD") from None
        if parsed.isoformat() != value:
            raise ValueError("invoice_date must use YYYY-MM-DD")
        return value

    @field_validator("taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False, max_fraction_digits=2)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"{getattr(info, 'field_name', 'amount')} must use canonical non-negative decimal text")
        if getattr(info, "field_name", None) == "iva_rate" and parsed > Decimal("100"):
            raise ValueError("iva_rate must not exceed 100")
        return value


class LedgerEvidenceAddProjection(BaseModel):
    """Allowlisted bounded evidence result for the exact submitted profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    record: LedgerEvidenceRecordProjection
    bucket_event_ids: _EvidenceEventIds

    @model_validator(mode="after")
    def _correlate_record(self) -> LedgerEvidenceAddProjection:
        if self.record.bucket_id != str(self.profile_id):
            raise ValueError("evidence add result belongs to another profile")
        return self


class LedgerEvidenceAddExecutionResult(BaseModel):
    """Private result wrapper kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceAddProjection

    @model_validator(mode="after")
    def _correlate_result(self) -> LedgerEvidenceAddExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence add execution result belongs to another profile")
        return self


@dataclass(frozen=True, slots=True)
class _PreparedAdd:
    service: PurchaseInvoiceEvidenceService
    candidate: PurchaseInvoiceEvidence
    execution_result: LedgerEvidenceAddExecutionResult


class LedgerEvidenceAddExecutor:
    """Commit one evidence add through the canonical service in exact-profile custody."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Bind the exact-profile evidence capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceAddRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Preflight the bounded result, then ingest and atomically append the record/event."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_ADD_PHASE)

        def preflight() -> _PreparedAdd:
            ports = self._ports_factory(bucket_id=bucket_id)
            evidence_repository = _require_exact_evidence_ports(ports, bucket_id=bucket_id)
            candidate = _candidate_record(payload, bucket_id=bucket_id)
            service = PurchaseInvoiceEvidenceService(ports=ports)
            event_ids = ("f" * 64,)
            execution_result = _execution_result(payload.profile_id, candidate, event_ids)
            _check_result_size(execution_result)
            if payload.idempotency_key is not None:
                prior_id = derive_keyed_purchase_invoice_evidence_id(
                    bucket_id=bucket_id,
                    idempotency_key=payload.idempotency_key,
                )
                rows, _revision = evidence_repository.load_revisioned(bucket_id=bucket_id)
                prior = next((row for row in rows if row.evidence_id == prior_id), None)
                if prior is not None:
                    _require_record_identity(prior, bucket_id=bucket_id, evidence_id=prior_id)
                    _check_result_size(_execution_result(payload.profile_id, prior, ()))
            return _PreparedAdd(service=service, candidate=candidate, execution_result=execution_result)

        async def capture() -> str:
            prepared = await asyncio.to_thread(preflight)
            async with context.cancellation.irreversible_section():
                # Attachment bytes and their manifest are durable secure-custody
                # writes inside add(), before the catalogue+event batch. UNKNOWN
                # is therefore required before entering the service.
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(
                    prepared.service.add,
                    bucket_id=bucket_id,
                    source_path=payload.source_path,
                    supplier=prepared.candidate.supplier,
                    invoice_number=prepared.candidate.invoice_number,
                    invoice_date=prepared.candidate.invoice_date,
                    taxable_base=prepared.candidate.taxable_base,
                    iva_rate=prepared.candidate.iva_rate,
                    iva_amount=prepared.candidate.iva_amount,
                    notes=prepared.candidate.notes,
                    actor="cli",
                    idempotency_key=payload.idempotency_key,
                )
                await context.events.effect(OperationEffect.UPDATED)
                _require_add_result(result, payload=payload, bucket_id=bucket_id)
                execution_result = _execution_result(
                    payload.profile_id,
                    result.record,
                    result.bucket_event_ids,
                )
                _check_result_size(execution_result)
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-add")


def _candidate_record(payload: LedgerEvidenceAddRequest, *, bucket_id: str) -> PurchaseInvoiceEvidence:
    """Validate domain constraints and maximum projection shape before ingestion."""
    occurred_at = now()
    return PurchaseInvoiceEvidence(
        evidence_id="0" * 16,
        bucket_id=bucket_id,
        source_path=payload.source_path,
        source_sha256="0" * 64,
        attachment_id="0" * 64,
        media_kind=MediaKind.PDF,
        supplier=payload.supplier,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        taxable_base=None if payload.taxable_base is None else Decimal(payload.taxable_base),
        iva_rate=None if payload.iva_rate is None else Decimal(payload.iva_rate),
        iva_amount=None if payload.iva_amount is None else Decimal(payload.iva_amount),
        notes=payload.notes,
        created_at=occurred_at,
        updated_at=occurred_at,
    )


def _execution_result(
    profile_id: UUID,
    record: PurchaseInvoiceEvidence,
    event_ids: tuple[str, ...],
) -> LedgerEvidenceAddExecutionResult:
    projection = LedgerEvidenceAddProjection(
        profile_id=profile_id,
        record=LedgerEvidenceRecordProjection.from_record(record),
        bucket_event_ids=event_ids,
    )
    return LedgerEvidenceAddExecutionResult(profile_id=profile_id, result=projection)


def _require_add_result(
    result: PurchaseInvoiceEvidenceResult,
    *,
    payload: LedgerEvidenceAddRequest,
    bucket_id: str,
) -> None:
    record = result.record
    expected_id = (
        derive_keyed_purchase_invoice_evidence_id(bucket_id=bucket_id, idempotency_key=payload.idempotency_key)
        if payload.idempotency_key is not None
        else None
    )
    if (
        record.bucket_id != bucket_id
        or record.attachment_id != record.source_sha256
        or (expected_id is not None and record.evidence_id != expected_id)
        or (expected_id is None and re.fullmatch(r"[0-9a-f]{16}", record.evidence_id) is None)
        or len(result.bucket_event_ids) not in ({0, 1} if expected_id is not None else {1})
        or (not result.bucket_event_ids and expected_id is None)
        or any(not event_id or len(event_id) > 64 for event_id in result.bucket_event_ids)
        or (result.bucket_event_ids and record.source_path != payload.source_path)
        or record.supplier != payload.supplier
        or record.invoice_number != payload.invoice_number
        or record.invoice_date != payload.invoice_date
        or record.taxable_base != (None if payload.taxable_base is None else Decimal(payload.taxable_base))
        or record.iva_rate != (None if payload.iva_rate is None else Decimal(payload.iva_rate))
        or record.iva_amount != (None if payload.iva_amount is None else Decimal(payload.iva_amount))
        or record.notes != payload.notes
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _require_worker_identity(
    *,
    request_definition_id: str,
    request_subject_ref: str,
    context: OperationExecutorContext,
    bucket_id: str,
) -> None:
    subject = profile_operation_subject(bucket_id)
    if (
        request_definition_id != LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID
        or context.identity.definition_id != LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID
        or request_subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_exact_evidence_ports(
    ports: LedgerEvidencePorts,
    *,
    bucket_id: str,
) -> RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol:
    evidence_objects = getattr(ports.evidence_repository, "secure_object_repository", None)
    event_objects = getattr(ports.bucket_event_repository, "secure_object_repository", None)
    if (
        evidence_objects is None
        or evidence_objects is not event_objects
        or not isinstance(ports.attachment_ingestor, ProfileBoundEvidenceAttachmentIngestorProtocol)
        or ports.attachment_ingestor.secure_object_repository is not evidence_objects
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if not isinstance(ports.evidence_repository, RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if not callable(getattr(ports.bucket_event_repository, "load_revisioned", None)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if bucket_id != require_active_bucket_id():
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports.evidence_repository


def _require_record_identity(record: PurchaseInvoiceEvidence, *, bucket_id: str, evidence_id: str) -> None:
    if record.bucket_id != bucket_id or record.evidence_id != evidence_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _check_result_size(result: BaseModel) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceAddExecutionResult:
        raise ValueError("invalid ledger evidence add execution result")
    profile_id = result.profile_id
    if (
        receipt.identity.definition_id != LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.UPDATED
    ):
        raise ValueError("ledger evidence add has an incompatible terminal receipt")
    return result.result


def _build_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    request_type = LedgerEvidenceAddRequest
    result_type = LedgerEvidenceAddExecutionResult
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=LedgerEvidenceAddExecutor,
            build=lambda: LedgerEvidenceAddExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_EVIDENCE_ADD_PHASE,),
        interaction_kinds=frozenset(),
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
            permitted_effects=frozenset({OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_ledger_evidence_add_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare one bounded exact-profile purchase-evidence add operation."""
    return _build_definition(ports_factory)


def resolve_ledger_evidence_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT for evidence add."""
    if request.definition_id != LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEvidenceAddRequest
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


def build_ledger_evidence_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, whole-profile access, and exact receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerEvidenceAddRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerEvidenceAddProjection,
        ),
        result_projector=_project_result,
        access_resolver=resolve_ledger_evidence_add_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_ADD_PHASE",
    "LedgerEvidenceAddExecutionResult",
    "LedgerEvidenceAddExecutor",
    "LedgerEvidenceAddProjection",
    "LedgerEvidenceAddRequest",
    "build_ledger_evidence_add_definition",
    "build_ledger_evidence_add_registration",
    "resolve_ledger_evidence_add_access",
]
