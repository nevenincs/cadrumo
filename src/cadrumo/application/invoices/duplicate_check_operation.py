"""Registered read of the stored invoice a document may already be; it writes nothing."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.duplicates import DuplicateBasis, likely_duplicate_invoice
from ...domain.iva.schema import InvoiceKind
from ..ledger.read_access import resolve_ledger_request_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .inspection_read_ports import InvoiceInspectionReadPortsFactory

LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID: Final = "ledger.invoice.duplicate"

_MAX_ASKED_TEXT: Final = 4_096
_AskedText = Annotated[str, Field(max_length=_MAX_ASKED_TEXT)]


class LedgerInvoiceDuplicateRequest(BaseModel):
    """What a document states, as read or corrected. Blank or unreadable facts match nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: InvoiceKind
    invoice_number: _AskedText | None = None
    counterparty_tax_id: _AskedText | None = None
    invoice_date: _AskedText | None = None
    grand_total: _AskedText | None = None


class LedgerInvoiceDuplicateResult(BaseModel):
    """The stored invoice found, if any, and what it shares with the document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    invoice_id: str | None = None
    basis: DuplicateBasis | None = None


class LedgerInvoiceDuplicateExecutionResult(BaseModel):
    """Worker-side envelope of the answer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerInvoiceDuplicateResult


def _date_stated(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text.strip()) if text else None
    except ValueError:
        return None


def _total_stated(text: str | None) -> Decimal | None:
    return try_parse_canonical_decimal(text, signed=False) if text else None


class LedgerInvoiceDuplicateExecutor:
    """Compare what a document states with the exact profile's stored invoices."""

    def __init__(self, factory: InvoiceInspectionReadPortsFactory) -> None:
        """Retain the declared invoice reader."""
        self._factory = factory

    def _answer(
        self, payload: LedgerInvoiceDuplicateRequest, operation: PinnedAuthorityOperation
    ) -> LedgerInvoiceDuplicateResult:
        profile = str(payload.profile_id)
        ports = self._factory(bucket_id=profile, operation=operation)
        if ports.bucket_id != profile or ports.invoices.bucket_id != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        catalogue = ports.invoices.load_authenticated()
        if any(bucket_id != profile for bucket_id in catalogue.attributed_bucket_ids()):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        stored = (catalogue.get(invoice_id) for invoice_id in sorted(catalogue.invoice_ids()))
        found = likely_duplicate_invoice(
            (invoice for invoice in stored if invoice is not None),
            kind=payload.kind,
            invoice_number=payload.invoice_number,
            counterparty_tax_id=payload.counterparty_tax_id,
            invoice_date=_date_stated(payload.invoice_date),
            grand_total=_total_stated(payload.grand_total),
        )
        return LedgerInvoiceDuplicateResult(
            profile_id=payload.profile_id,
            invoice_id=found.invoice_id if found is not None else None,
            basis=found.basis if found is not None else None,
        )

    async def execute(
        self,
        request: OperationRequest[LedgerInvoiceDuplicateRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from its stored invoices."""
        payload = request.payload
        if request.definition_id != LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID)
        result = await asyncio.to_thread(self._answer, payload, context.authority_operation)
        return await context.operands.put(LedgerInvoiceDuplicateExecutionResult(result=result), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerInvoiceDuplicateExecutionResult:
        raise ValueError("invalid ledger invoice duplicate result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger invoice duplicate has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_invoice_duplicate_definition(factory: InvoiceInspectionReadPortsFactory) -> OperationDefinition:
    """Declare the exact-profile read of a document's likely duplicate."""
    return build_single_phase_definition(
        definition_id=LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID,
        request_type=LedgerInvoiceDuplicateRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerInvoiceDuplicateExecutionResult,
        executor_type=LedgerInvoiceDuplicateExecutor,
        build=lambda: LedgerInvoiceDuplicateExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_invoice_duplicate_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID,
        request_type=LedgerInvoiceDuplicateRequest,
    )


def build_ledger_invoice_duplicate_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerInvoiceDuplicateResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_invoice_duplicate_access,
    )


__all__ = [
    "LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID",
    "LedgerInvoiceDuplicateExecutor",
    "LedgerInvoiceDuplicateRequest",
    "LedgerInvoiceDuplicateResult",
    "build_ledger_invoice_duplicate_definition",
    "build_ledger_invoice_duplicate_registration",
    "resolve_ledger_invoice_duplicate_access",
]
