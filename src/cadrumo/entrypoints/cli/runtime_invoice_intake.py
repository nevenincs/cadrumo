"""Authenticated CLI bridges for invoice import and guided invoice intake."""

from __future__ import annotations

from pathlib import Path
from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID,
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceWizardOutcome,
    InvoiceWizardProjection,
    InvoiceWizardRequest,
)
from ...application.invoices.catalogue_intake_refusal import (
    INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.aggregation import IntracomOperationType
from ...core.hashing import sha256_file
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ._ledger_support import ledger_invoice_validation_no_recovery
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def _submit[ProjectionT: BaseModel](
    request: BaseModel,
    *,
    client: RuntimeFrontendClient,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one intake request through the invocation's immutable profile client."""
    if getattr(request, "profile_id", None) != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )


def submit_invoice_import(
    ctx: typer.Context,
    *,
    source_path: Path,
    kind: InvoiceKind,
    country: str | None,
) -> InvoiceImportProjection:
    """Import one secure-reference invoice book and correlate its row effects."""
    try:
        absolute_path = source_path.resolve(strict=True)
        source_sha256 = sha256_file(absolute_path)
    except OSError as exc:
        error = InvoiceValidationError(
            "bulk invoice import file could not be read",
            translated_message="application.invoices.bulk_import.errors.file_read_failed",
            context={"path_name": source_path.name, "error_type": type(exc).__name__},
        )
        if (refusal := ledger_invoice_validation_no_recovery(error)) is not None:
            raise refusal from exc
        raise error from exc

    client = bound_profile_client(ctx)
    request = InvoiceImportRequest(
        profile_id=client.profile_id,
        kind=kind,
        source_path=str(absolute_path),
        source_sha256=source_sha256,
        country=country,
    )
    completed = _submit(
        request,
        client=client,
        definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
        result_type=InvoiceImportProjection,
    )
    projection = completed.projection
    expected_effect = (
        OperationEffect.NONE
        if projection.created == 0
        else OperationEffect.PARTIAL
        if projection.refused
        else OperationEffect.UPDATED
    )
    if (
        projection.profile_id != client.profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return projection


def submit_invoice_wizard(
    ctx: typer.Context,
    *,
    kind: InvoiceKind,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str,
    iva_rate: str | None,
    currency: str,
    country_code: str,
    operation_date: str | None,
    notes: str,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    retention_rate: str | None,
    retention_amount: str | None,
    invoice_class: str | None,
    series: str | None,
    rectifies_invoice_number: str | None,
    recargo_amount: str | None,
) -> InvoiceWizardProjection:
    """Validate and create one manually entered invoice in its bound worker."""
    client = bound_profile_client(ctx)
    request = InvoiceWizardRequest(
        profile_id=client.profile_id,
        kind=kind,
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        currency=currency,
        country_code=country_code,
        operation_date=operation_date,
        notes=notes,
        iva_category=iva_category.value if iva_category is not None else None,
        operation_type=operation_type,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        recargo_amount=recargo_amount,
    )
    completed = _submit(
        request,
        client=client,
        definition_id=INVOICE_WIZARD_OPERATION_DEFINITION_ID,
        result_type=InvoiceWizardOutcome,
    )
    outcome = completed.projection
    if outcome.profile_id != client.profile_id:
        raise invalid_completion_error(completed)
    if outcome.outcome == "refused":
        _raise_invoice_wizard_refusal(completed, outcome, client.profile_id)

    return _invoice_wizard_success(completed, outcome, client.profile_id, kind)


__all__ = ["submit_invoice_import", "submit_invoice_wizard"]


def _raise_invoice_wizard_refusal(
    completed: RegisteredOperationCompletion[InvoiceWizardOutcome], outcome: InvoiceWizardOutcome, profile_id: UUID
) -> Never:
    """Translate only a correlated prewrite wizard refusal and retain its receipt."""
    refusal = outcome.refusal
    if (
        refusal is None
        or outcome.result is not None
        or refusal.profile_id != profile_id
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
    ):
        raise invalid_completion_error(completed)
    error = refusal.to_validation_error()
    rendered = ledger_invoice_validation_no_recovery(error)
    if rendered is None or rendered.context is None:
        raise invalid_completion_error(completed)
    rendered.context.update(
        {
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": completed.refusal_code,
        }
    )
    raise rendered


def _invoice_wizard_success(
    completed: RegisteredOperationCompletion[InvoiceWizardOutcome],
    outcome: InvoiceWizardOutcome,
    profile_id: UUID,
    kind: InvoiceKind,
) -> InvoiceWizardProjection:
    """Correlate the created or reused invoice and successful receipt."""
    projection = outcome.result
    if projection is None or outcome.refusal is not None:
        raise invalid_completion_error(completed)
    expected_effect = OperationEffect.NONE if projection.already_existed else OperationEffect.UPDATED
    if (
        _invoice_wizard_identity_invalid(projection, profile_id, kind)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return projection


def _invoice_wizard_identity_invalid(projection: InvoiceWizardProjection, profile_id: UUID, kind: InvoiceKind) -> bool:
    """Require exact invoice profile ownership and kind."""
    return (
        projection.profile_id != profile_id
        or projection.invoice.bucket_id is None
        or str(projection.invoice.bucket_id) != str(profile_id)
        or (projection.invoice.kind is not kind)
    )
