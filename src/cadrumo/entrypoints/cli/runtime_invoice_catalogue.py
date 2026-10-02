"""Authenticated CLI reads of the canonical invoice catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

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
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.classification import InvoiceKind
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)

_REFUSAL_LOCALES = {
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
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or completed.refusal_code != INVOICE_ADD_VALIDATION_REFUSAL_CODE
            or result.validation_code is None
            or result.invoice is not None
            or (result.validation_code == "duplicate_invoice") != (result.invoice_id is not None)
        )
    else:
        invoice = result.invoice
        invalid = invalid or (
            invoice is None
            or (invoice.bucket_id is not None and str(invoice.bucket_id) != str(client.profile_id))
            or invoice.kind is not request.kind
            or invoice.invoice_number != request.invoice_number
            or invoice.issued_at != request.issued_at
            or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.effect is not OperationEffect.UPDATED
            or completed.refusal_code is not None
        )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
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
        or any(
            row.bucket_id is not None and str(row.bucket_id) != str(client.profile_id) for row in projection.invoices
        )
        or any(kind is not None and row.kind is not kind for row in projection.invoices)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
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
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or not invoice_id.strip()
            or not invoice.invoice_id.startswith(invoice_id.strip())
            or (invoice.bucket_id is not None and str(invoice.bucket_id) != str(client.profile_id))
        )
        if not invalid:
            return InvoiceCatalogueViewRead(completion=completed, invoice=invoice)
    else:
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != INVOICE_VIEW_REFUSAL_CODE
            or (outcome.reason is InvoiceLookupRefusalReason.REQUIRED) != (not invoice_id.strip())
            or any(not candidate.startswith(invoice_id.strip()) for candidate in outcome.candidate_ids)
        )
        if not invalid:
            raise CliRefusedBoundaryError(
                translated_message=_REFUSAL_LOCALES[outcome.reason],
                context={
                    "operation_id": str(completed.operation_id),
                    "terminal_condition": completed.terminal_condition.value,
                    "effect": completed.effect.value,
                    "refusal_code": INVOICE_VIEW_REFUSAL_CODE,
                    "invoice_id": invoice_id.strip(),
                    "candidates": ", ".join(outcome.candidate_ids),
                },
            )
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
    if (
        projection.profile_id != client.profile_id
        or projection.invoice_id != invoice_id
        or not invoice_id.strip()
        or not projection.invoice.invoice_id.startswith(invoice_id.strip())
        or (projection.invoice.bucket_id is not None and str(projection.invoice.bucket_id) != str(client.profile_id))
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
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
    if (
        projection.profile_id != client.profile_id
        or projection.invoice_id != invoice_id
        or not invoice_id.strip()
        or not projection.invoice.invoice_id.startswith(invoice_id.strip())
        or (projection.invoice.bucket_id is not None and str(projection.invoice.bucket_id) != str(client.profile_id))
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
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
