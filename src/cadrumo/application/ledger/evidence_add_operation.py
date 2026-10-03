"""Registered exact-profile creation of purchase-invoice evidence."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceResult,
    PurchaseInvoiceEvidenceService,
    derive_keyed_purchase_invoice_evidence_id,
)
from .evidence_port_identity import require_exact_evidence_ports
from .evidence_ports import LedgerEvidencePortsFactory
from .evidence_read_operation import LedgerEvidenceRecordProjection
from .read_access import resolve_ledger_commit_access

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
    source_directory: _EvidencePath
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
            evidence_repository = require_exact_evidence_ports(ports, bucket_id=bucket_id)
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
                    source_directory=Path(payload.source_directory),
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
    expected_id = (
        derive_keyed_purchase_invoice_evidence_id(bucket_id=bucket_id, idempotency_key=payload.idempotency_key)
        if payload.idempotency_key is not None
        else None
    )
    _require_add_record_identity(result.record, bucket_id=bucket_id, expected_id=expected_id)
    _require_add_event_receipt(result, payload=payload, expected_id=expected_id)
    _require_submitted_record_fields(result.record, payload=payload)


def _require_add_record_identity(
    record: PurchaseInvoiceEvidence,
    *,
    bucket_id: str,
    expected_id: str | None,
) -> None:
    if (
        record.bucket_id != bucket_id
        or record.attachment_id != record.source_sha256
        or (expected_id is not None and record.evidence_id != expected_id)
        or (expected_id is None and re.fullmatch(r"[0-9a-f]{16}", record.evidence_id) is None)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _require_add_event_receipt(
    result: PurchaseInvoiceEvidenceResult,
    *,
    payload: LedgerEvidenceAddRequest,
    expected_id: str | None,
) -> None:
    record = result.record
    if len(result.bucket_event_ids) not in ({0, 1} if expected_id is not None else {1}):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if not result.bucket_event_ids and expected_id is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if any(not event_id or len(event_id) > 64 for event_id in result.bucket_event_ids):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if result.bucket_event_ids and record.source_path != payload.source_path:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _require_submitted_record_fields(record: PurchaseInvoiceEvidence, *, payload: LedgerEvidenceAddRequest) -> None:
    _require_submitted_invoice_fields(record, payload=payload)
    _require_submitted_amounts(record, payload=payload)


def _require_submitted_invoice_fields(record: PurchaseInvoiceEvidence, *, payload: LedgerEvidenceAddRequest) -> None:
    if (
        record.supplier != payload.supplier
        or record.invoice_number != payload.invoice_number
        or record.invoice_date != payload.invoice_date
        or record.notes != payload.notes
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _require_submitted_amounts(record: PurchaseInvoiceEvidence, *, payload: LedgerEvidenceAddRequest) -> None:
    if (
        record.taxable_base != (None if payload.taxable_base is None else Decimal(payload.taxable_base))
        or record.iva_rate != (None if payload.iva_rate is None else Decimal(payload.iva_rate))
        or record.iva_amount != (None if payload.iva_amount is None else Decimal(payload.iva_amount))
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


def _require_record_identity(record: PurchaseInvoiceEvidence, *, bucket_id: str, evidence_id: str) -> None:
    if record.bucket_id != bucket_id or record.evidence_id != evidence_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _check_result_size(result: BaseModel) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceAddExecutionResult:
        raise ValueError("invalid ledger evidence add execution result")
    _require_add_success_receipt(receipt, profile_id=result.profile_id)
    return result.result


def _require_add_success_receipt(receipt: OperationTerminalReceipt, *, profile_id: UUID) -> None:
    message = "ledger evidence add has an incompatible terminal receipt"
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=message,
    )


def _build_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    request_type = LedgerEvidenceAddRequest
    result_type = LedgerEvidenceAddExecutionResult
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        request_type=request_type,
        result_type=result_type,
        executor_type=LedgerEvidenceAddExecutor,
        build=lambda: LedgerEvidenceAddExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
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
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_evidence_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, whole-profile access, and exact receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceAddProjection,
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
