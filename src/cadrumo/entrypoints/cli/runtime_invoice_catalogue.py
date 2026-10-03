"""Authenticated CLI reads of the canonical invoice catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.invoices.catalogue_add_operation import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from ...application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_REFUSAL_CODE,
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceViewProjection,
    InvoiceViewRefusal,
    InvoiceViewRequest,
    InvoiceViewSuccess,
)
from ...application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ...application.invoices.catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveRequest,
    InvoiceRemoveResult,
)
from ...application.invoices.catalogue_selection import InvoiceLookupRefusalReason
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdatePatch,
    InvoiceUpdateRequest,
    InvoiceUpdateResult,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.classification import InvoiceKind
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation

_REFUSAL_LOCALE_KEYS = {
    InvoiceLookupRefusalReason.REQUIRED: "application.invoices.lifecycle.errors.invoice_id_required",
    InvoiceLookupRefusalReason.NOT_FOUND: "application.invoices.lifecycle.errors.invoice_not_found",
    InvoiceLookupRefusalReason.AMBIGUOUS: "application.invoices.lifecycle.errors.ambiguous_invoice_prefix",
}


@dataclass(frozen=True, slots=True)
class InvoiceCatalogueListRead:
    """Keep the completed inventory receipt through CLI presentation."""

    completion: RegisteredOperationCompletion[InvoiceListProjection]
    invoices: tuple[CatalogueInvoiceSnapshot, ...]


@dataclass(frozen=True, slots=True)
class InvoiceCatalogueViewRead:
    """Keep the selected invoice's completed receipt through presentation."""

    completion: RegisteredOperationCompletion[InvoiceViewProjection]
    invoice: CatalogueInvoiceSnapshot


def add_invoice_catalogue(
    ctx: typer.Context, *, request: InvoiceAddRequest
) -> tuple[RegisteredOperationCompletion[InvoiceAddResult], InvoiceAddResult]:
    """Create one catalogue invoice inside the invocation's exact profile worker."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceAddResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    invalid = result.profile_id != client.profile_id
    if result.outcome == "validation_error":
        invalid = invalid or (invalid_invoice_add_refusal(completed, result))
    else:
        invoice = result.invoice
        invalid = invalid or (invalid_invoice_add_success(completed, invoice, request, client.profile_id))
    if invalid:
        raise invalid_completion_error(completed)
    return completed, result


def read_invoice_catalogue(ctx: typer.Context, *, kind: InvoiceKind | None) -> InvoiceCatalogueListRead:
    """Read an ordered whole-profile catalogue inside its selected worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        InvoiceListRequest(profile_id=client.profile_id, kind=kind),
        definition_id=INVOICE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceListProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.kind is not kind
        or any(invoice_has_wrong_profile(row, client.profile_id) for row in projection.invoices)
        or any(invoice_has_wrong_kind(row, kind) for row in projection.invoices)
        or (completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED)
        or (completed.effect is not OperationEffect.NONE)
        or (completed.refusal_code is not None)
    ):
        raise invalid_completion_error(completed)
    return InvoiceCatalogueListRead(completion=completed, invoices=projection.invoices)


def view_invoice_catalogue(ctx: typer.Context, *, invoice_id: str) -> InvoiceCatalogueViewRead:
    """Resolve an exact ID or prefix under guarded result disclosure."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        InvoiceViewRequest(profile_id=client.profile_id, invoice_id=invoice_id),
        definition_id=INVOICE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceViewProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    outcome = projection.outcome
    invalid = (
        projection.profile_id != client.profile_id
        or projection.invoice_id != invoice_id
        or completed.effect is not OperationEffect.NONE
    )
    if isinstance(outcome, InvoiceViewSuccess):
        invoice = outcome.invoice
        invalid = invalid or (invalid_invoice_view_success(completed, invoice, invoice_id, client.profile_id))
        if not invalid:
            return InvoiceCatalogueViewRead(completion=completed, invoice=invoice)
    else:
        invalid = invalid or (invalid_invoice_view_refusal(completed, outcome, invoice_id))
        if not invalid:
            raise CliRefusedBoundaryError(
                translated_message=_REFUSAL_LOCALE_KEYS[outcome.reason],
                context={
                    "operation_id": str(completed.operation_id),
                    "terminal_condition": completed.terminal_condition.value,
                    "effect": completed.effect.value,
                    "refusal_code": INVOICE_VIEW_REFUSAL_CODE,
                    "invoice_id": invoice_id.strip(),
                    "candidates": ", ".join(outcome.candidate_ids),
                },
            )
    raise invalid_completion_error(completed)


def remove_invoice_catalogue(
    ctx: typer.Context, *, invoice_id: str
) -> tuple[RegisteredOperationCompletion[InvoiceRemoveResult], CatalogueInvoiceSnapshot]:
    """Remove one selected record through the invocation's immutable profile client."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        InvoiceRemoveRequest(profile_id=client.profile_id, invoice_id=invoice_id),
        definition_id=INVOICE_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceRemoveResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if invalid_selected_invoice_mutation(completed, projection, invoice_id, client.profile_id):
        raise invalid_completion_error(completed)
    return completed, projection.invoice


def update_invoice_catalogue(
    ctx: typer.Context, *, invoice_id: str, patch: InvoiceUpdatePatch
) -> tuple[RegisteredOperationCompletion[InvoiceUpdateResult], InvoiceUpdateResult]:
    """Update one selected record through the invocation's immutable profile client."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        InvoiceUpdateRequest(profile_id=client.profile_id, invoice_id=invoice_id, patch=patch),
        definition_id=INVOICE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceUpdateResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if invalid_selected_invoice_mutation(completed, projection, invoice_id, client.profile_id):
        raise invalid_completion_error(completed)
    return completed, projection


__all__ = [
    "InvoiceCatalogueListRead",
    "InvoiceCatalogueViewRead",
    "add_invoice_catalogue",
    "read_invoice_catalogue",
    "remove_invoice_catalogue",
    "update_invoice_catalogue",
    "view_invoice_catalogue",
]


def invalid_invoice_add_refusal(
    completed: RegisteredOperationCompletion[InvoiceAddResult], result: InvoiceAddResult
) -> bool:
    """Require a no-effect refusal with bounded duplicate-invoice guidance."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != INVOICE_ADD_VALIDATION_REFUSAL_CODE
        or (result.validation_code is None)
        or (result.invoice is not None)
        or ((result.validation_code == "duplicate_invoice") != (result.invoice_id is not None))
    )


def invalid_invoice_add_success(
    completed: RegisteredOperationCompletion[InvoiceAddResult],
    invoice: CatalogueInvoiceSnapshot | None,
    request: InvoiceAddRequest,
    profile_id: UUID,
) -> bool:
    """Require the created invoice and updated receipt to match the request."""
    return (
        invoice is None
        or (invoice.bucket_id is not None and str(invoice.bucket_id) != str(profile_id))
        or invoice.kind is not request.kind
        or (invoice.invoice_number != request.invoice_number)
        or (invoice.issued_at != request.issued_at)
        or (completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED)
        or (completed.effect is not OperationEffect.UPDATED)
        or (completed.refusal_code is not None)
    )


def invalid_invoice_view_success(
    completed: RegisteredOperationCompletion[InvoiceViewProjection],
    invoice: CatalogueInvoiceSnapshot,
    invoice_id: str,
    profile_id: UUID,
) -> bool:
    """Require the selected prefix and profile to match a successful read."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or (not invoice_id.strip())
        or (not invoice.invoice_id.startswith(invoice_id.strip()))
        or (invoice.bucket_id is not None and str(invoice.bucket_id) != str(profile_id))
    )


def invalid_invoice_view_refusal(
    completed: RegisteredOperationCompletion[InvoiceViewProjection], outcome: InvoiceViewRefusal, invoice_id: str
) -> bool:
    """Require bounded lookup guidance to match the submitted invoice prefix."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code != INVOICE_VIEW_REFUSAL_CODE
        or (outcome.reason is InvoiceLookupRefusalReason.REQUIRED) != (not invoice_id.strip())
        or any(not candidate.startswith(invoice_id.strip()) for candidate in outcome.candidate_ids)
    )


def invoice_has_wrong_profile(invoice: CatalogueInvoiceSnapshot, profile_id: UUID) -> bool:
    """Reject a catalogue row bound to another profile."""
    return invoice.bucket_id is not None and str(invoice.bucket_id) != str(profile_id)


def invoice_has_wrong_kind(invoice: CatalogueInvoiceSnapshot, kind: InvoiceKind | None) -> bool:
    """Reject a row that does not match the requested catalogue filter."""
    return kind is not None and invoice.kind is not kind


class _SelectedInvoiceMutation(Protocol):
    """A mutation result that names the profile and the one invoice it changed."""

    @property
    def profile_id(self) -> UUID:
        """Return the profile that owns the changed invoice."""
        ...

    @property
    def invoice_id(self) -> str:
        """Return the invoice handle the mutation was submitted with."""
        ...

    @property
    def invoice(self) -> CatalogueInvoiceSnapshot:
        """Return the resolved invoice snapshot."""
        ...


def invalid_selected_invoice_mutation[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
    result: _SelectedInvoiceMutation,
    invoice_id: str,
    profile_id: UUID,
) -> bool:
    """Require the updated receipt and the resolved invoice to match the submitted handle and profile."""
    return (
        result.profile_id != profile_id
        or result.invoice_id != invoice_id
        or not invoice_id.strip()
        or not result.invoice.invoice_id.startswith(invoice_id.strip())
        or (result.invoice.bucket_id is not None and str(result.invoice.bucket_id) != str(profile_id))
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    )
