"""Exact-profile reviewed invoice confirmation operation."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.async_cleanup import await_cancellation_complete
from ...core.confirmation_gate import FindingResolutionAction
from ...core.country_code import CountryCodeAlpha2
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ...domain.iva.supply_nature import SupplyNature
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .confirmation_gate import FindingResolution
from .invoice_confirmation import (
    PreparedInvoiceConfirmation,
    persist_prepared_invoice_confirmation,
    prepare_invoice_confirmation_from_evidence,
)
from .invoice_evidence_operation import (
    InvoiceEvidenceDecimalText,
    InvoiceEvidenceLabel,
    InvoiceEvidenceNote,
    InvoiceEvidenceOperationPortsFactory,
    InvoiceEvidenceReference,
    check_invoice_evidence_result_size,
    invoice_evidence_operation_capabilities,
    require_bound_invoice_evidence_ports,
    require_invoice_evidence_terminal_success,
    resolve_invoice_evidence_authority_legends,
)
from .invoice_evidence_operation_dtos import (
    InvoiceConfirmationProjectionV1,
)
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID = "ledger.evidence.confirm"


class FindingResolutionInputV1(BaseModel):
    """Bounded wire form restored to the canonical finding-resolution record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    blocker_id: Annotated[str, Field(min_length=16, max_length=16)]
    action: FindingResolutionAction
    value: InvoiceEvidenceLabel | None = None
    note: InvoiceEvidenceNote = ""

    def to_resolution(self) -> FindingResolution:
        """Restore the canonical one-blocker decision and its validation."""
        return FindingResolution(blocker_id=self.blocker_id, action=self.action, value=self.value, note=self.note)


class LedgerEvidenceConfirmRequest(BaseModel):
    """Complete one-document operator statement, bound to a reviewed draft."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: InvoiceEvidenceReference | None = None
    attachment_id: InvoiceEvidenceReference | None = None
    expected_source_sha256: Hex64Str
    expected_draft_review_sha256: Hex64Str
    kind: InvoiceKind
    counterparty_country: CountryCodeAlpha2 = "ES"
    counterparty_tax_id: InvoiceEvidenceLabel | None = None
    counterparty_name: InvoiceEvidenceLabel | None = None
    invoice_number: InvoiceEvidenceLabel | None = None
    invoice_date: date | None = None
    taxable_base: InvoiceEvidenceDecimalText | None = None
    iva_rate: InvoiceEvidenceDecimalText | None = None
    iva_amount: InvoiceEvidenceDecimalText | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    iva_category: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: InvoiceEvidenceDecimalText | None = None
    retention_amount: InvoiceEvidenceDecimalText | None = None
    recargo_amount: InvoiceEvidenceDecimalText | None = None
    invoice_class: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    supply_nature: SupplyNature | None = None
    series: InvoiceEvidenceLabel | None = None
    rectifies_invoice_number: InvoiceEvidenceLabel | None = None
    notes: InvoiceEvidenceNote = ""
    resolutions: Annotated[tuple[FindingResolutionInputV1, ...], Field(max_length=128)] = ()

    @field_validator("taxable_base", "iva_rate", "iva_amount", "retention_rate", "retention_amount", "recargo_amount")
    @classmethod
    def _canonical_decimal(cls, value: str | None) -> str | None:
        """Reject malformed figures before they become a durable operation."""
        _decimal(value)
        return value

    @model_validator(mode="after")
    def _one_reference(self) -> Self:
        if (self.evidence_id is None) == (self.attachment_id is None):
            raise ValueError("exactly one evidence or attachment reference is required")
        return self


class LedgerEvidenceConfirmProjection(BaseModel):
    """Canonical invoice result and the re-read draft used to confirm it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: InvoiceEvidenceReference | None = None
    attachment_id: InvoiceEvidenceReference | None = None
    source_sha256: Hex64Str
    reviewed_draft_sha256: Hex64Str
    confirmation: InvoiceConfirmationProjectionV1


class LedgerEvidenceConfirmExecutionResult(BaseModel):
    """Encrypted worker confirmation result scoped to the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceConfirmProjection


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid decimal confirmation field") from None
    if not parsed.is_finite() or str(parsed) != value:
        raise ValueError("confirmation decimal must be finite and canonical")
    return parsed


class LedgerEvidenceConfirmExecutor:
    """Re-read the reviewed source, then write exactly one canonical confirmation."""

    def __init__(self, ports_factory: InvoiceEvidenceOperationPortsFactory) -> None:
        """Bind the exact-profile confirmation capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[LedgerEvidenceConfirmRequest], context: OperationExecutorContext
    ) -> str:
        """Check the reviewed source before entering canonical write custody."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        ports = self._ports_factory(bucket_id=bucket_id)
        require_bound_invoice_evidence_ports(ports, bucket_id=bucket_id)

        def prepare() -> PreparedInvoiceConfirmation:
            return prepare_invoice_confirmation_from_evidence(
                bucket_id=bucket_id,
                kind=payload.kind,
                counterparty_country=payload.counterparty_country,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                counterparty_tax_id=payload.counterparty_tax_id,
                counterparty_name=payload.counterparty_name,
                invoice_number=payload.invoice_number,
                invoice_date=payload.invoice_date,
                taxable_base=_decimal(payload.taxable_base),
                iva_rate=_decimal(payload.iva_rate),
                iva_amount=_decimal(payload.iva_amount),
                currency=payload.currency,
                iva_category=None if payload.iva_category is None else IvaCategory(payload.iva_category),
                operation_type=payload.operation_type,
                operation_date=payload.operation_date,
                retention_rate=_decimal(payload.retention_rate),
                retention_amount=_decimal(payload.retention_amount),
                recargo_amount=_decimal(payload.recargo_amount),
                invoice_class_token=payload.invoice_class,
                supply_nature=payload.supply_nature,
                series=payload.series,
                rectifies_invoice_number=payload.rectifies_invoice_number,
                notes=payload.notes,
                resolutions=tuple(row.to_resolution() for row in payload.resolutions),
                expected_source_sha256=payload.expected_source_sha256,
                expected_draft_review_sha256=payload.expected_draft_review_sha256,
                settings=ports.settings,
                catalogue_creation_ports=ports.catalogue_creation_ports,
                counterparty_establishment_repository=ports.counterparty_establishment_repository,
                evidence_ports=ports.evidence_ports,
                extraction_ports=ports.extraction_ports,
                operation=context.authority_operation,
                legends=resolve_invoice_evidence_authority_legends(context),
            )

        async def prepare_persist_capture() -> str:
            prepared = await asyncio.to_thread(prepare)
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                confirmation = await asyncio.to_thread(
                    persist_prepared_invoice_confirmation,
                    prepared,
                    confirmed_by=f"operation:{context.identity.operation_id}",
                    catalogue_creation_ports=ports.catalogue_creation_ports,
                    invoice_confirmation_ports=ports.invoice_confirmation_ports,
                    evidence_ports=ports.evidence_ports,
                )
                await context.events.effect(OperationEffect.UPDATED)
            result = LedgerEvidenceConfirmProjection(
                profile_id=payload.profile_id,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                source_sha256=payload.expected_source_sha256,
                reviewed_draft_sha256=payload.expected_draft_review_sha256,
                confirmation=InvoiceConfirmationProjectionV1.from_result(confirmation),
            )
            check_invoice_evidence_result_size(result)
            return await context.operands.put(
                LedgerEvidenceConfirmExecutionResult(profile_id=payload.profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(prepare_persist_capture(), task_name="ledger-evidence-confirm")


def build_ledger_evidence_confirm_definition(
    ports_factory: InvoiceEvidenceOperationPortsFactory,
) -> OperationDefinition:
    """Register one reviewed invoice confirmation with canonical audit writes."""
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceConfirmRequest,
        result_type=LedgerEvidenceConfirmExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerEvidenceConfirmRequest,
            executor_type=LedgerEvidenceConfirmExecutor,
            build=lambda: LedgerEvidenceConfirmExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=invoice_evidence_operation_capabilities(mutates=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _project_confirm(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceConfirmExecutionResult:
        raise ValueError("invalid invoice confirmation result")
    require_invoice_evidence_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({OperationEffect.UPDATED}),
    )
    if result.result.profile_id != result.profile_id:
        raise ValueError("invoice confirmation result belongs to another profile")
    return result.result


def _resolve_confirm_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if (
        request.definition_id != LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID
        or type(request.payload) is not LedgerEvidenceConfirmRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_evidence_confirm_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind all-period tax disclosure and UPDATED confirmation receipts."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerEvidenceConfirmRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=2,
            model_type=LedgerEvidenceConfirmProjection,
        ),
        result_projector=_project_confirm,
        access_resolver=_resolve_confirm_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID",
    "FindingResolutionInputV1",
    "LedgerEvidenceConfirmExecutionResult",
    "LedgerEvidenceConfirmExecutor",
    "LedgerEvidenceConfirmProjection",
    "LedgerEvidenceConfirmRequest",
    "build_ledger_evidence_confirm_definition",
    "build_ledger_evidence_confirm_registration",
]
