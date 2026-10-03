"""Guarded creation of one canonical invoice inside profile worker custody."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
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
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.invoice_legal_classification import resolve_invoice_legal_classification_catalogue
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.calculations.registry.iva_rate_kind_catalogue import (
    IvaRateKindCatalogue,
    resolve_iva_rate_kind_catalogue,
)
from ...domain.invoices.enums import IvaRate, iva_rate_slots_on
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaRateKind
from ..ledger.read_access import resolve_ledger_read_access
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
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
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
from .catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from .catalogue_creation_ports import CatalogueCreationPorts, CatalogueCreationPortsFactory
from .catalogue_read_projection import CatalogueInvoiceSnapshot
from .simplificada_advisory import SimplificadaTaxIdAdvisory, resolve_simplificada_tax_id_advisory

INVOICE_ADD_OPERATION_DEFINITION_ID = "ledger.invoice.add"
INVOICE_ADD_VALIDATION_REFUSAL_CODE = "REFUSED_INVOICE_ADD_VALIDATION"
_DUPLICATE_INVOICE_TRANSLATION = "application.invoices.creation.errors.duplicate_invoice"


class InvoiceAddLine(BaseModel):
    """Closed JSON-safe line input resolved into a dated canonical line by the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    description: str = Field(min_length=1, max_length=4096)
    quantity: PublicDecimal
    unit_price: PublicDecimal
    subtotal: PublicDecimal
    iva_rate: str = Field(min_length=1, max_length=128)
    iva_amount: PublicDecimal
    spending_category_id: str | None = Field(default=None, max_length=128)
    oss_rate_kind: str | None = Field(default=None, max_length=128)

    @classmethod
    def from_invoice_line(cls, line: InvoiceLine) -> InvoiceAddLine:
        """Copy one parsed CLI line into its closed secure-reference wire form."""
        return cls(
            description=line.description,
            quantity=PublicDecimal(decimal=str(line.quantity)),
            unit_price=PublicDecimal(decimal=str(line.unit_price)),
            subtotal=PublicDecimal(decimal=str(line.subtotal)),
            iva_rate=str(line.iva_rate),
            iva_amount=PublicDecimal(decimal=str(line.iva_amount)),
            spending_category_id=line.spending_category_id,
            oss_rate_kind=None if line.oss_rate_kind is None else str(line.oss_rate_kind),
        )

    def to_invoice_line(
        self,
        *,
        rate_slots: tuple[IvaRate, ...],
        rate_kind_catalogue: IvaRateKindCatalogue | None,
    ) -> InvoiceLine:
        """Project tokens from already-resolved catalogues and refuse unknown input."""
        iva_rate = next((slot for slot in rate_slots if str(slot) == self.iva_rate), None)
        if iva_rate is None:
            raise InvoiceValidationError("invoice line IVA rate is not declared by the active registry")
        oss_rate_kind: IvaRateKind | None = None
        if self.oss_rate_kind is not None:
            normalized_kind = self.oss_rate_kind.strip()
            oss_rate_kind = (
                None
                if rate_kind_catalogue is None
                else next(
                    (
                        definition.token
                        for definition in rate_kind_catalogue.definitions
                        if str(definition.token) == normalized_kind
                    ),
                    None,
                )
            )
            if oss_rate_kind is None:
                raise InvoiceValidationError("invoice line OSS rate kind is not declared by the active registry")
        return InvoiceLine(
            description=self.description,
            quantity=Decimal(self.quantity.decimal),
            unit_price=Decimal(self.unit_price.decimal),
            subtotal=Decimal(self.subtotal.decimal),
            iva_rate=iva_rate,
            iva_amount=Decimal(self.iva_amount.decimal),
            spending_category_id=self.spending_category_id,
            oss_rate_kind=oss_rate_kind,
        )


class InvoiceAddRequest(BaseModel):
    """Private exact-profile request matching the rich direct-add command."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: InvoiceKind
    counterparty_name: str = Field(min_length=1)
    counterparty_tax_id: str | None = None
    counterparty_country: str = Field(min_length=2, max_length=2)
    invoice_number: str = Field(min_length=1)
    issued_at: date
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    currency: str = Field(min_length=1, max_length=16)
    notes: str = ""
    iva_category: str | None = Field(default=None, min_length=1, max_length=128)
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: PublicDecimal | None = None
    retention_amount: PublicDecimal | None = None
    invoice_class: str | None = Field(default=None, min_length=1, max_length=64)
    series: str | None = None
    rectifies_invoice_number: str | None = None
    recargo_amount: PublicDecimal | None = None
    lines: tuple[InvoiceAddLine, ...] = ()

    @model_validator(mode="after")
    def _line_input_shape(self) -> InvoiceAddRequest:
        if self.lines and (self.taxable_base is not None or self.iva_rate is not None):
            raise ValueError("structured invoice lines cannot be combined with taxable_base or iva_rate")
        if not self.lines and self.taxable_base is None:
            raise ValueError("taxable_base is required when structured invoice lines are not supplied")
        return self


class InvoiceAddResult(BaseModel):
    """Safe creation receipt or bounded pre-write refusal detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    invoice: CatalogueInvoiceSnapshot | None = None
    invoice_id: str | None = None
    bucket_event_ids: tuple[str, ...] = Field(default=(), max_length=1)
    euro_value_pending: bool = False
    simplificada_tax_id_advisory_required: bool = False
    validation_code: Literal["invalid_invoice", "duplicate_invoice"] | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> InvoiceAddResult:
        if self.outcome == "created":
            if (
                self.invoice is None
                or self.invoice.bucket_id is None
                or str(self.invoice.bucket_id) != str(self.profile_id)
                or len(self.bucket_event_ids) != 1
                or self.invoice_id is not None
                or self.validation_code is not None
            ):
                raise ValueError("created invoice result is incomplete or belongs to another profile")
        elif (
            self.invoice is not None
            or self.bucket_event_ids
            or self.euro_value_pending
            or self.simplificada_tax_id_advisory_required
            or self.validation_code is None
            or (self.validation_code == "duplicate_invoice") != (self.invoice_id is not None)
        ):
            raise ValueError("invoice validation refusal detail is incomplete")
        return self

    @classmethod
    def validation_refusal(
        cls,
        profile_id: UUID,
        *,
        code: Literal["invalid_invoice", "duplicate_invoice"],
        invoice_id: str | None = None,
    ) -> InvoiceAddResult:
        """Build a safe detail for a deterministic refusal before invoice creation."""
        return cls(
            outcome="validation_error",
            profile_id=profile_id,
            invoice_id=invoice_id,
            validation_code=code,
        )

    @classmethod
    def created(
        cls,
        profile_id: UUID,
        *,
        invoice: CatalogueInvoiceSnapshot,
        bucket_event_ids: tuple[str, ...],
        euro_value_pending: bool,
        simplificada_tax_id_advisory_required: bool,
    ) -> InvoiceAddResult:
        """Build a successful invoice receipt with worker-resolved advisories."""
        return cls(
            outcome="created",
            profile_id=profile_id,
            invoice=invoice,
            bucket_event_ids=bucket_event_ids,
            euro_value_pending=euro_value_pending,
            simplificada_tax_id_advisory_required=simplificada_tax_id_advisory_required,
        )


class InvoiceAddExecutionResult(BaseModel):
    """Private secure operand whose public value is correlated with settlement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InvoiceAddResult


def project_invoice_add_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InvoiceAddResult:
    """Release only a created invoice or a typed validation refusal with a matching receipt."""
    if type(result) is not InvoiceAddExecutionResult:
        raise ValueError("invalid invoice-add execution result")
    private = InvoiceAddExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    public = private.result
    if (
        receipt.identity.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(public.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice-add result differs from its terminal receipt")
    if public.outcome == "created":
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.effect is not OperationEffect.UPDATED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
        ):
            raise ValueError("invoice-add success has an incompatible terminal receipt")
    elif (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != INVOICE_ADD_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or public.validation_code is None
    ):
        raise ValueError("invoice-add refusal has an incompatible terminal receipt")
    return public


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
        if (
            request.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(INVOICE_ADD_OPERATION_DEFINITION_ID)

        authority_operation = context.authority_operation

        def prepare() -> tuple[CatalogueCreationPorts, Invoice, bool]:
            ports = self._factory(bucket_id=profile)
            effective_date = payload.operation_date or payload.issued_at
            with validating_governed_facts(authority_operation):
                # Resolve each required vocabulary before checking request
                # membership. An absent or corrupt authority remains a
                # RegistryValidationError; only a token missing from a
                # successfully resolved catalogue becomes input validation.
                rate_slots = iva_rate_slots_on(effective_date) if payload.lines else ()
                rate_kind_catalogue = (
                    resolve_iva_rate_kind_catalogue(
                        effective_date=effective_date,
                        authority=authority_operation,
                    )
                    if any(line.oss_rate_kind is not None for line in payload.lines)
                    else None
                )
                category_catalogue = (
                    resolve_iva_category_catalogue(
                        effective_date=effective_date,
                        authority=authority_operation,
                    )
                    if payload.iva_category is not None
                    else None
                )
                invoice_class_catalogue = (
                    resolve_invoice_legal_classification_catalogue() if payload.invoice_class is not None else None
                )
                category_input = payload.iva_category
                if category_input is None:
                    iva_category = None
                else:
                    if category_catalogue is None:
                        raise RuntimeError("IVA category catalogue was not resolved for a supplied category")
                    iva_category = next(
                        (
                            category
                            for category in category_catalogue.all_categories
                            if str(category) == category_input.strip()
                        ),
                        None,
                    )
                    if iva_category is None:
                        raise InvoiceValidationError("IVA category is not declared by the active registry")

                invoice_class_input = payload.invoice_class
                if invoice_class_input is None:
                    invoice_class = None
                else:
                    if invoice_class_catalogue is None:
                        raise RuntimeError("invoice-class catalogue was not resolved for a supplied class")
                    invoice_class = next(
                        (
                            token
                            for token in invoice_class_catalogue.invoice_class_choices
                            if str(token) == invoice_class_input.strip()
                        ),
                        None,
                    )
                    if invoice_class is None:
                        raise InvoiceValidationError("invoice class is not declared by the active registry")
                lines = tuple(
                    line.to_invoice_line(
                        rate_slots=rate_slots,
                        rate_kind_catalogue=rate_kind_catalogue,
                    )
                    for line in payload.lines
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
                retention_amount=(
                    None if payload.retention_amount is None else Decimal(payload.retention_amount.decimal)
                ),
                invoice_class=invoice_class,
                series=payload.series,
                rectifies_invoice_number=payload.rectifies_invoice_number,
                recargo_amount=(None if payload.recargo_amount is None else Decimal(payload.recargo_amount.decimal)),
                lines=lines or None,
                rate_provider=ports.rate_provider,
                operation=authority_operation,
            )
            if invoice.bucket_id is None or str(invoice.bucket_id) != profile:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            advisory_required = (
                resolve_simplificada_tax_id_advisory(invoice=invoice) is SimplificadaTaxIdAdvisory.REQUIRED
            )
            return ports, invoice, advisory_required

        async def record_refusal(
            code: Literal["invalid_invoice", "duplicate_invoice"],
            *,
            invoice_id: str | None = None,
        ) -> OperationRefusalEvidence:
            detail = InvoiceAddExecutionResult(
                result=InvoiceAddResult.validation_refusal(payload.profile_id, code=code, invoice_id=invoice_id)
            )
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=INVOICE_ADD_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        try:
            ports, invoice, advisory_required = await asyncio.to_thread(prepare)
        except (InvoiceValidationError, ValidationError):
            async with context.cancellation.irreversible_section():
                return await record_refusal("invalid_invoice")

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.effect(OperationEffect.UNKNOWN)

                def persist():
                    with validating_governed_facts(authority_operation):
                        return create_catalogue_invoice(invoice=invoice, ports=ports, actor="runtime")

                try:
                    created = await asyncio.to_thread(persist)
                except InvoiceValidationError as error:
                    if error.translated_message != _DUPLICATE_INVOICE_TRANSLATION:
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return await record_refusal("duplicate_invoice", invoice_id=invoice.invoice_id)
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

        return await await_cancellation_complete(commit(), task_name="invoice-add-publication")


def build_invoice_add_definition(factory: CatalogueCreationPortsFactory) -> OperationDefinition:
    """Declare a durable, guarded add with honest uncertain effects."""
    return OperationDefinition(
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        request_type=InvoiceAddRequest,
        result_type=InvoiceAddExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=InvoiceAddRequest,
            executor_type=InvoiceAddExecutor,
            build=lambda: InvoiceAddExecutor(factory),
        ),
        phase_codes=(INVOICE_ADD_OPERATION_DEFINITION_ID,),
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
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        refusal_detail_codes=frozenset({INVOICE_ADD_VALIDATION_REFUSAL_CODE}),
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
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
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_invoice_add_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll exact request and bounded result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=InvoiceAddRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=InvoiceAddResult
        ),
        access_resolver=resolve_invoice_add_access,
        result_projector=project_invoice_add_result,
    )


__all__ = [
    "INVOICE_ADD_OPERATION_DEFINITION_ID",
    "INVOICE_ADD_VALIDATION_REFUSAL_CODE",
    "InvoiceAddExecutionResult",
    "InvoiceAddExecutor",
    "InvoiceAddLine",
    "InvoiceAddRequest",
    "InvoiceAddResult",
    "build_invoice_add_definition",
    "build_invoice_add_registration",
    "project_invoice_add_result",
    "resolve_invoice_add_access",
]
