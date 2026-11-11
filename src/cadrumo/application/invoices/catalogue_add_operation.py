"""Guarded creation of one canonical invoice inside profile worker custody."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, DecimalException
from typing import Literal

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CoreValidationError, InternalInvariantError
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import reading_dated_facts_below_support
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
from ...domain.invoices.business_premises import BusinessPremisesLease
from ...domain.invoices.enums import InvoiceClass, IvaRate, iva_rate_slots_on
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.schema import IvaCategory
from ..ledger.read_access import resolve_ledger_request_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.error_detail import operation_refusal_words
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
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
from .catalogue_creation import (
    CatalogueInvoiceCreateResult,
    build_catalogue_invoice,
    create_catalogue_invoice,
)
from .catalogue_creation_ports import (
    CatalogueCreationPorts,
    CatalogueCreationPortsFactory,
    CatalogueInvoiceRateProviderPort,
)
from .catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceDocumentIndex
from .simplificada_advisory import SimplificadaTaxIdAdvisory, resolve_simplificada_tax_id_advisory

_DUPLICATE_INVOICE_TRANSLATION = "application.invoices.creation.errors.duplicate_invoice"

_PERSON_FRONTEND_ACTOR = "runtime"


class InvoiceAddExecutor:
    """Call the canonical creation functions under the runtime commit fence."""

    def __init__(
        self,
        factory: CatalogueCreationPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the worker's bucket-scoped creation-port composition and caller reader."""
        self._factory = factory
        self._execution_caller_reader = execution_caller_reader

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
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_PERSON_FRONTEND_ACTOR)
        try:
            ports, invoice, advisory_required = await asyncio.to_thread(
                prepare_invoice_add,
                factory=self._factory,
                payload=payload,
                profile=profile,
                authority_operation=authority_operation,
            )
        except (InvoiceValidationError, ValidationError) as error:
            async with context.cancellation.irreversible_section():
                return await _record_invoice_add_refusal(context, payload, "invalid_invoice", refused_by=error)
        except RegistryValidationError as error:
            if not invoice_date_outside_registry_support(
                payload.operation_date or payload.issued_at,
                authority_operation,
            ):
                raise
            async with context.cancellation.irreversible_section():
                return await _record_invoice_add_refusal(context, payload, "invalid_invoice", refused_by=error)
        except (CoreValidationError, DecimalException) as error:
            # After the registry clause: RegistryValidationError is a CoreValidationError too.
            async with context.cancellation.irreversible_section():
                return await _record_invoice_add_refusal(context, payload, "invalid_invoice", refused_by=error)
        return await await_cancellation_complete(
            _commit_invoice_add(
                context=context,
                payload=payload,
                profile=profile,
                authority_operation=authority_operation,
                ports=ports,
                invoice=invoice,
                advisory_required=advisory_required,
                actor=actor,
            ),
            task_name="invoice-add-publication",
        )


async def _record_invoice_add_refusal(
    context: OperationExecutorContext,
    payload: InvoiceAddRequest,
    code: Literal["invalid_invoice", "duplicate_invoice"],
    *,
    invoice_id: str | None = None,
    refused_by: BaseException,
) -> OperationRefusalEvidence:
    detail = InvoiceAddExecutionResult(
        result=InvoiceAddResult.validation_refusal(
            payload.profile_id, code=code, invoice_id=invoice_id, words=operation_refusal_words(refused_by)
        )
    )
    detail_ref = await context.operands.put(detail, written_at=now())
    return OperationRefusalEvidence(refusal_code=INVOICE_ADD_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)


def _persist_invoice_add(
    *,
    authority_operation: PinnedAuthorityOperation,
    ports: CatalogueCreationPorts,
    invoice: Invoice,
    actor: str,
) -> tuple[CatalogueInvoiceCreateResult, InvoiceDocumentIndex]:
    with validating_governed_facts(authority_operation):
        created = create_catalogue_invoice(invoice=invoice, ports=ports, actor=actor)
    return created, InvoiceDocumentIndex.read(ports.documents)


async def _commit_invoice_add(
    *,
    context: OperationExecutorContext,
    payload: InvoiceAddRequest,
    profile: str,
    authority_operation: PinnedAuthorityOperation,
    ports: CatalogueCreationPorts,
    invoice: Invoice,
    advisory_required: bool,
    actor: str,
) -> str | OperationRefusalEvidence:
    async with context.cancellation.irreversible_section():
        if require_active_bucket_id() != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.effect(OperationEffect.UNKNOWN)
        try:
            created, documents = await asyncio.to_thread(
                _persist_invoice_add,
                authority_operation=authority_operation,
                ports=ports,
                invoice=invoice,
                actor=actor,
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
                refused_by=error,
            )
        if (
            created.invoice.invoice_id != invoice.invoice_id
            or created.invoice.bucket_id is None
            or created.invoice.bucket_id != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        result = InvoiceAddResult.created(
            payload.profile_id,
            invoice=CatalogueInvoiceSnapshot.from_invoice(created.invoice, documents=documents),
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
        raise InternalInvariantError("IVA category catalogue was not resolved for a supplied category")
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
        raise InternalInvariantError("invoice-class catalogue was not resolved for a supplied class")
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


def declared_invoice_category(
    category_input: str | None,
    *,
    effective_date: date,
    authority_operation: PinnedAuthorityOperation,
) -> IvaCategory | None:
    """Read a stated IVA category as add reads it, under the governed scope the caller holds."""
    return _invoice_add_category(
        category_input,
        _resolve_invoice_add_category_catalogue(
            category_input,
            effective_date=effective_date,
            authority_operation=authority_operation,
        ),
    )


def declared_invoice_class(class_input: str | None) -> InvoiceClass | None:
    """Read a stated invoice class as add reads it, under the governed scope the caller holds."""
    return _invoice_add_class(class_input, _resolve_invoice_add_class_catalogue(class_input))


def invoice_date_outside_registry_support(on_date: date, operation: PinnedAuthorityOperation) -> bool:
    """Tell a date the registry does not serve from a registry failure on one it does."""
    return not operation.supported_filing_years().date_envelope().admits_coordinate(on_date)


def invoice_add_lease(
    payload: InvoiceAddRequest,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> BusinessPremisesLease | None:
    """Re-enter the domain owner for the lease the transport carries as plain text."""
    with validating_governed_facts(authority_operation):
        return None if payload.business_premises_lease is None else payload.business_premises_lease.to_domain()


def build_invoice_from_add_request(
    *,
    payload: InvoiceAddRequest,
    business_premises_lease: BusinessPremisesLease | None,
    profile: str,
    authority_operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
) -> tuple[Invoice, bool]:
    """Construct the validated invoice an add request names, and whether its advisory applies.

    This is the whole of acceptance short of the commit, and it touches no repository.
    """
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
        business_premises_lease=business_premises_lease,
        lines=lines or None,
        rate_provider=rate_provider,
        operation=authority_operation,
    )
    _require_prepared_invoice_profile(invoice, profile)
    advisory_required = resolve_simplificada_tax_id_advisory(invoice=invoice) is SimplificadaTaxIdAdvisory.REQUIRED
    return invoice, advisory_required


def prepare_invoice_add(
    *,
    factory: CatalogueCreationPortsFactory,
    payload: InvoiceAddRequest,
    profile: str,
    authority_operation: PinnedAuthorityOperation,
) -> tuple[CatalogueCreationPorts, Invoice, bool]:
    """Build the invoice, ports and advisory flag for an invoice add request."""
    # The transport carries plain text; re-enter the domain owner before port creation.
    business_premises_lease = invoice_add_lease(payload, authority_operation=authority_operation)
    ports = factory(bucket_id=profile)
    # An invoice older than the filing years is still a dated record: its facts
    # are read as a projection, and filing never reaches this scope.
    with reading_dated_facts_below_support():
        invoice, advisory_required = build_invoice_from_add_request(
            payload=payload,
            business_premises_lease=business_premises_lease,
            profile=profile,
            authority_operation=authority_operation,
            rate_provider=ports.rate_provider,
        )
    return ports, invoice, advisory_required


def _require_prepared_invoice_profile(invoice: Invoice, profile: str) -> None:
    if invoice.bucket_id is None or invoice.bucket_id != profile:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def build_invoice_add_definition(
    factory: CatalogueCreationPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare a durable, guarded add with honest uncertain effects.

    ``execution_caller_reader`` names the frontend and session that admitted an
    execution, so an automation's creation event is recorded under its session's
    label.
    """
    return build_single_phase_definition(
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        request_type=InvoiceAddRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InvoiceAddExecutionResult,
        executor_type=InvoiceAddExecutor,
        build=lambda: InvoiceAddExecutor(factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        refusal_detail_codes=frozenset({INVOICE_ADD_VALIDATION_REFUSAL_CODE}),
    )


def resolve_invoice_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger rights and a fresh COMMIT grant."""
    return resolve_ledger_request_commit_access(
        request, context, definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID, request_type=InvoiceAddRequest
    )


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
    "build_invoice_from_add_request",
    "declared_invoice_category",
    "declared_invoice_class",
    "invoice_add_lease",
    "invoice_date_outside_registry_support",
    "resolve_invoice_add_access",
]
