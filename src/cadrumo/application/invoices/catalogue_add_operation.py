"""Guarded creation of one canonical invoice inside profile worker custody."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.invoice_legal_classification import (
    InvoiceLegalClassificationCatalogue,
    resolve_invoice_legal_classification_catalogue,
)
from ...domain.calculations.registry.iva_category_catalogue import (
    IvaCategoryCatalogue,
    resolve_iva_category_catalogue,
)
from ...domain.calculations.registry.iva_rate_kind_catalogue import (
    IvaRateKindCatalogue,
    resolve_iva_rate_kind_catalogue,
)
from ...domain.invoices.enums import InvoiceClass, IvaRate, iva_rate_slots_on
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.schema import IvaCategory
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddExecutionResult,
    InvoiceAddLine,
    InvoiceAddRequest,
    InvoiceAddResult,
    project_invoice_add_result,
)
from .catalogue_creation import CatalogueInvoiceCreateResult, build_catalogue_invoice, create_catalogue_invoice
from .catalogue_creation_ports import CatalogueCreationPorts, CatalogueCreationPortsFactory
from .catalogue_read_projection import CatalogueInvoiceSnapshot
from .simplificada_advisory import SimplificadaTaxIdAdvisory, resolve_simplificada_tax_id_advisory

_DUPLICATE_INVOICE_TRANSLATION = "application.invoices.creation.errors.duplicate_invoice"


class InvoiceAddExecutor:
    """Call the canonical creation functions under the runtime commit fence."""

    def __init__(self, factory: CatalogueCreationPortsFactory) -> None:
        """Retain the worker's bucket-scoped creation-port composition."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[InvoiceAddRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Keep the commit fence through catalogue mutation and secure receipt publication."""
        payload = request.payload
        profile = str(payload.profile_id)
        if request.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(INVOICE_ADD_OPERATION_DEFINITION_ID)

        authority_operation = context.authority_operation
        try:
            ports, invoice, advisory_required = await asyncio.to_thread(
                _prepare_invoice_add,
                factory=self._factory,
                payload=payload,
                profile=profile,
                authority_operation=authority_operation,
            )
        except (InvoiceValidationError, ValidationError):
            async with context.cancellation.irreversible_section():
                return await _record_invoice_add_refusal(context, payload, "invalid_invoice")
        return await await_cancellation_complete(
            _commit_invoice_add(
                context=context,
                payload=payload,
                profile=profile,
                authority_operation=authority_operation,
                ports=ports,
                invoice=invoice,
                advisory_required=advisory_required,
            ),
            task_name="invoice-add-publication",
        )


async def _record_invoice_add_refusal(
    context: OperationExecutorContext,
    payload: InvoiceAddRequest,
    code: Literal["invalid_invoice", "duplicate_invoice"],
    *,
    invoice_id: str | None = None,
) -> OperationRefusalEvidence:
    detail = InvoiceAddExecutionResult(
        result=InvoiceAddResult.validation_refusal(payload.profile_id, code=code, invoice_id=invoice_id)
    )
    detail_ref = await context.operands.put(detail, written_at=now())
    return OperationRefusalEvidence(refusal_code=INVOICE_ADD_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)


def _persist_invoice_add(
    *,
    authority_operation: PinnedAuthorityOperation,
    ports: CatalogueCreationPorts,
    invoice: Invoice,
) -> CatalogueInvoiceCreateResult:
    with validating_governed_facts(authority_operation):
        return create_catalogue_invoice(invoice=invoice, ports=ports, actor="runtime")


async def _commit_invoice_add(
    *,
    context: OperationExecutorContext,
    payload: InvoiceAddRequest,
    profile: str,
    authority_operation: PinnedAuthorityOperation,
    ports: CatalogueCreationPorts,
    invoice: Invoice,
    advisory_required: bool,
) -> str | OperationRefusalEvidence:
    async with context.cancellation.irreversible_section():
        if require_active_bucket_id() != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.effect(OperationEffect.UNKNOWN)
        try:
            created = await asyncio.to_thread(
                _persist_invoice_add,
                authority_operation=authority_operation,
                ports=ports,
                invoice=invoice,
            )
        except InvoiceValidationError as error:
            if error.translated_message != _DUPLICATE_INVOICE_TRANSLATION:
                raise
            await context.events.effect(OperationEffect.NONE)
            return await _record_invoice_add_refusal(
                context,
                payload,
                "duplicate_invoice",
                invoice_id=invoice.invoice_id,
            )
        if (
            created.invoice.invoice_id != invoice.invoice_id
            or created.invoice.bucket_id is None
            or str(created.invoice.bucket_id) != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        result = InvoiceAddResult.created(
            payload.profile_id,
            invoice=CatalogueInvoiceSnapshot.from_invoice(created.invoice),
            bucket_event_ids=created.bucket_event_ids,
            euro_value_pending=created.invoice.euro_value_pending,
            simplificada_tax_id_advisory_required=advisory_required,
        )
        await context.events.effect(OperationEffect.UPDATED)
        return await context.operands.put(InvoiceAddExecutionResult(result=result), written_at=now())


def _resolve_invoice_add_category_catalogue(
    category_input: str | None,
    *,
    effective_date: date,
    authority_operation: PinnedAuthorityOperation,
) -> IvaCategoryCatalogue | None:
    return (
        resolve_iva_category_catalogue(effective_date=effective_date, authority=authority_operation)
        if category_input is not None
        else None
    )


def _invoice_add_category(
    category_input: str | None,
    category_catalogue: IvaCategoryCatalogue | None,
) -> IvaCategory | None:
    if category_input is None:
        return None
    if category_catalogue is None:
        raise RuntimeError("IVA category catalogue was not resolved for a supplied category")
    category = next(
        (token for token in category_catalogue.all_categories if str(token) == category_input.strip()),
        None,
    )
    if category is None:
        raise InvoiceValidationError("IVA category is not declared by the active registry")
    return category


def _resolve_invoice_add_class_catalogue(class_input: str | None) -> InvoiceLegalClassificationCatalogue | None:
    return resolve_invoice_legal_classification_catalogue() if class_input is not None else None


def _invoice_add_class(
    class_input: str | None,
    class_catalogue: InvoiceLegalClassificationCatalogue | None,
) -> InvoiceClass | None:
    if class_input is None:
        return None
    if class_catalogue is None:
        raise RuntimeError("invoice-class catalogue was not resolved for a supplied class")
    invoice_class = next(
        (token for token in class_catalogue.invoice_class_choices if str(token) == class_input.strip()),
        None,
    )
    if invoice_class is None:
        raise InvoiceValidationError("invoice class is not declared by the active registry")
    return invoice_class


def _resolve_invoice_add_rate_kind_catalogue(
    lines: tuple[InvoiceAddLine, ...],
    *,
    effective_date: date,
    authority_operation: PinnedAuthorityOperation,
) -> IvaRateKindCatalogue | None:
    if not any(line.oss_rate_kind is not None for line in lines):
        return None
    return resolve_iva_rate_kind_catalogue(effective_date=effective_date, authority=authority_operation)


def _invoice_add_lines(
    request_lines: tuple[InvoiceAddLine, ...],
    *,
    rate_slots: tuple[IvaRate, ...],
    rate_kind_catalogue: IvaRateKindCatalogue | None,
) -> tuple[InvoiceLine, ...]:
    return tuple(
        line.to_invoice_line(rate_slots=rate_slots, rate_kind_catalogue=rate_kind_catalogue) for line in request_lines
    )


def _prepare_invoice_add(
    *,
    factory: CatalogueCreationPortsFactory,
    payload: InvoiceAddRequest,
    profile: str,
    authority_operation: PinnedAuthorityOperation,
) -> tuple[CatalogueCreationPorts, Invoice, bool]:
    ports = factory(bucket_id=profile)
    effective_date = payload.operation_date or payload.issued_at
    with validating_governed_facts(authority_operation):
        # Resolve required vocabularies before validating request membership so
        # corrupt authority remains a registry failure, not input validation.
        rate_slots = iva_rate_slots_on(effective_date) if payload.lines else ()
        rate_kind_catalogue = _resolve_invoice_add_rate_kind_catalogue(
            payload.lines,
            effective_date=effective_date,
            authority_operation=authority_operation,
        )
        category_catalogue = _resolve_invoice_add_category_catalogue(
            payload.iva_category,
            effective_date=effective_date,
            authority_operation=authority_operation,
        )
        class_catalogue = _resolve_invoice_add_class_catalogue(payload.invoice_class)
        iva_category = _invoice_add_category(payload.iva_category, category_catalogue)
        invoice_class = _invoice_add_class(payload.invoice_class, class_catalogue)
        lines = _invoice_add_lines(
            payload.lines,
            rate_slots=rate_slots,
            rate_kind_catalogue=rate_kind_catalogue,
        )
    invoice = build_catalogue_invoice(
        bucket_id=profile,
        kind=payload.kind,
        counterparty_name=payload.counterparty_name,
        counterparty_tax_id=payload.counterparty_tax_id,
        counterparty_country=payload.counterparty_country,
        invoice_number=payload.invoice_number,
        issued_at=payload.issued_at,
        taxable_base=(None if payload.taxable_base is None else Decimal(payload.taxable_base.decimal)),
        iva_rate=(None if payload.iva_rate is None else Decimal(payload.iva_rate.decimal)),
        currency=payload.currency,
        notes=payload.notes,
        iva_category=iva_category,
        operation_type=payload.operation_type,
        operation_date=payload.operation_date,
        retention_rate=(None if payload.retention_rate is None else Decimal(payload.retention_rate.decimal)),
        retention_amount=(None if payload.retention_amount is None else Decimal(payload.retention_amount.decimal)),
        invoice_class=invoice_class,
        series=payload.series,
        rectifies_invoice_number=payload.rectifies_invoice_number,
        recargo_amount=(None if payload.recargo_amount is None else Decimal(payload.recargo_amount.decimal)),
        lines=lines or None,
        rate_provider=ports.rate_provider,
        operation=authority_operation,
    )
    _require_prepared_invoice_profile(invoice, profile)
    advisory_required = resolve_simplificada_tax_id_advisory(invoice=invoice) is SimplificadaTaxIdAdvisory.REQUIRED
    return ports, invoice, advisory_required


def _require_prepared_invoice_profile(invoice: Invoice, profile: str) -> None:
    if invoice.bucket_id is None or str(invoice.bucket_id) != profile:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def build_invoice_add_definition(factory: CatalogueCreationPortsFactory) -> OperationDefinition:
    """Declare a durable, guarded add with honest uncertain effects."""
    return build_single_phase_definition(
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        request_type=InvoiceAddRequest,
        result_type=InvoiceAddExecutionResult,
        executor_type=InvoiceAddExecutor,
        build=lambda: InvoiceAddExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=frozenset({INVOICE_ADD_VALIDATION_REFUSAL_CODE}),
    )


def resolve_invoice_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger rights and a fresh COMMIT grant."""
    if request.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InvoiceAddRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    return with_commit_action(resolved)


def build_invoice_add_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll exact request and bounded result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceAddResult,
        result_projector=project_invoice_add_result,
        access_resolver=resolve_invoice_add_access,
    )


__all__ = [
    "InvoiceAddExecutor",
    "build_invoice_add_definition",
    "build_invoice_add_registration",
    "resolve_invoice_add_access",
]
