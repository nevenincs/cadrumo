"""Exact-profile runtime bridge for one registered Google Sheets export."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.export.google_operation import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GoogleSheetsExportOperationRequest,
    GoogleSheetsExportPublicResultV1,
)
from ...core.errors.error_codes import ErrorCategory, get_registered_error_code_by_code
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_registered_operation import run_registered_operation


def google_operation_error(code: str, *, diagnostic_ref: str | None) -> Exception:
    """Project a supervised export failure through canonical ErrorCode metadata."""
    error_code = get_registered_error_code_by_code(code)
    if error_code.category not in {ErrorCategory.ERROR, ErrorCategory.INTERNAL}:
        return CliRefusedBoundaryError(translated_message=error_code.message_key)
    return InternalInvariantError(f"supervised Google Sheets export failed ({diagnostic_ref or 'no diagnostic'})")


def _project_registered_refusal(error: CliRefusedBoundaryError) -> NoReturn:
    """Keep the established localized Google export refusal surface."""
    context = error.context
    code = context.get("reason") if context is not None else None
    if not isinstance(code, str) or not code.startswith(
        ("REFUSED_GOOGLE_SHEETS_EXPORT_", "FAIL_GOOGLE_SHEETS_EXPORT_", "ERROR_GOOGLE_SHEETS_EXPORT_")
    ):
        raise error
    raise google_operation_error(code, diagnostic_ref=None) from None


def run_google_sheets_export(
    client: RuntimeFrontendClient,
    *,
    modelo: str,
    period: str,
    year: int,
    prefill_relations: bool = False,
    dry_run: bool = False,
) -> tuple[str, GoogleSheetsExportPublicResultV1]:
    """Run a registered export bound to the profile admitted for this CLI invocation."""
    request = GoogleSheetsExportOperationRequest(
        profile_id=client.profile_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        prefill_relations=prefill_relations,
        dry_run=dry_run,
    )
    subject_ref = profile_operation_subject(str(client.profile_id))
    try:
        completed = run_registered_operation(
            client,
            request,
            definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=subject_ref,
            result_type=GoogleSheetsExportPublicResultV1,
            request_version=1,
            result_version=1,
            timeout=120,
        )
    except CliRefusedBoundaryError as error:
        _project_registered_refusal(error)

    projection = completed.projection
    expected_effect = OperationEffect.NONE if dry_run else OperationEffect.UPDATED
    if _google_export_receipt_invalid(completed, projection, request, client.profile_id, expected_effect, dry_run):
        raise invalid_completion_error(completed)
    return str(client.profile_id), projection


__all__ = ["google_operation_error", "run_google_sheets_export"]


def _google_export_receipt_invalid(
    completed: RegisteredOperationCompletion[GoogleSheetsExportPublicResultV1],
    projection: GoogleSheetsExportPublicResultV1,
    request: GoogleSheetsExportOperationRequest,
    profile_id: UUID,
    expected_effect: OperationEffect,
    dry_run: bool,
) -> bool:
    """Correlate the requested filing scope, dry-run mode, and exact settled export effect."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (projection.profile_id != profile_id)
        or (projection.modelo != request.modelo)
        or (projection.period != request.filing_period.registry_token)
        or (projection.filing_year != request.filing_year)
        or (projection.dry_run is not dry_run)
    )
