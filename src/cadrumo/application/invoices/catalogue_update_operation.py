"""Guarded update of one canonical invoice inside profile worker custody."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.invoices.enums import PaymentStatus
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_scalar import PublicDecimal
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_lifecycle import CatalogueInvoicePatch, update_catalogue_invoice
from .catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
from .catalogue_read_projection import CatalogueInvoiceSnapshot

INVOICE_UPDATE_OPERATION_DEFINITION_ID = "ledger.invoice.update"


class InvoiceUpdateValues(BaseModel):
    """Wire-safe correction values; selection is carried by the patch field mask."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    counterparty_name: str | None = None
    counterparty_country: str | None = None
    notes: str | None = None
    payment_status: PaymentStatus | None = None
    iva_category: str | None = Field(default=None, min_length=1)
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: PublicDecimal | None = None
    retention_amount: PublicDecimal | None = None
    series: str | None = None
    invoice_class: str | None = Field(default=None, min_length=1)
    rectifies_invoice_number: str | None = None
    payment_id: str | None = None


class InvoiceUpdatePatch(BaseModel):
    """Explicit field mask preserves omitted values through full wire serialization."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    values: InvoiceUpdateValues
    fields: frozenset[str]

    @model_validator(mode="after")
    def _field_mask(self) -> InvoiceUpdatePatch:
        if not self.fields or not self.fields <= CatalogueInvoicePatch.model_fields.keys():
            raise ValueError("invoice patch must select supported correction fields")
        if any(value is not None and name not in self.fields for name, value in self.values.model_dump().items()):
            raise ValueError("invoice patch contains an unselected value")
        return self

    @classmethod
    def from_patch(cls, patch: CatalogueInvoicePatch) -> InvoiceUpdatePatch:
        """Capture the caller's intentional fields before transport expands defaults."""
        values = patch.model_dump(exclude_unset=True)
        for name in ("retention_rate", "retention_amount"):
            value = values.get(name)
            if value is not None:
                values[name] = PublicDecimal(decimal=str(value))
        return cls(values=InvoiceUpdateValues.model_validate(values), fields=frozenset(patch.model_fields_set))

    def to_patch(self) -> CatalogueInvoicePatch:
        """Restore canonical lifecycle omission semantics after transport."""
        values = self.values.model_dump(include=set(self.fields))
        for name, value in (
            ("retention_rate", self.values.retention_rate),
            ("retention_amount", self.values.retention_amount),
        ):
            if name in self.fields and value is not None:
                values[name] = Decimal(value.decimal)
        return CatalogueInvoicePatch.model_validate(values)


class InvoiceUpdateRequest(BaseModel):
    """Exact profile and selected record or unambiguous prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str = Field(min_length=1, max_length=64)
    patch: InvoiceUpdatePatch


class InvoiceUpdateResult(BaseModel):
    """Committed record snapshot, held as an encrypted operation operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str
    invoice: CatalogueInvoiceSnapshot
    bucket_event_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _identity(self) -> InvoiceUpdateResult:
        if (
            not self.invoice_id.strip()
            or not self.invoice.invoice_id.startswith(self.invoice_id.strip())
            or (self.invoice.bucket_id is not None and str(self.invoice.bucket_id) != str(self.profile_id))
        ):
            raise ValueError("updated invoice differs from requested identity")
        return self


class InvoiceUpdateExecutor:
    """Use the existing lifecycle service under the runtime commit fence."""

    def __init__(self, factory: CatalogueLifecyclePortsFactory) -> None:
        """Retain the worker's lifecycle port composition."""
        self._factory = factory

    async def execute(self, request: OperationRequest[InvoiceUpdateRequest], context: OperationExecutorContext) -> str:
        """Keep the commit fence through correction and encrypted receipt publication."""
        payload = request.payload
        profile = str(payload.profile_id)
        if request.definition_id != INVOICE_UPDATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(INVOICE_UPDATE_OPERATION_DEFINITION_ID)

        def update() -> InvoiceUpdateResult:
            ports = self._factory(bucket_id=profile)
            updated = update_catalogue_invoice(
                bucket_id=profile,
                invoice_id=payload.invoice_id,
                patch=payload.patch.to_patch(),
                ports=ports,
                actor="runtime",
            )
            return InvoiceUpdateResult(
                profile_id=payload.profile_id,
                invoice_id=payload.invoice_id,
                invoice=CatalogueInvoiceSnapshot.from_invoice(updated.invoice),
                bucket_event_ids=updated.bucket_event_ids,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(update)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="invoice-update-publication")


def build_invoice_update_definition(factory: CatalogueLifecyclePortsFactory) -> OperationDefinition:
    """Declare one durable, guarded update with honest uncertain effects."""
    return build_single_phase_definition(
        definition_id=INVOICE_UPDATE_OPERATION_DEFINITION_ID,
        request_type=InvoiceUpdateRequest,
        result_type=InvoiceUpdateResult,
        executor_type=InvoiceUpdateExecutor,
        build=lambda: InvoiceUpdateExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_invoice_update_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger rights and a fresh commit fence."""
    if request.definition_id != INVOICE_UPDATE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InvoiceUpdateRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    return with_commit_action(resolved)


def build_invoice_update_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceUpdateResult,
        access_resolver=resolve_invoice_update_access,
    )
