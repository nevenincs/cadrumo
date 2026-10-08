"""CLI bridge for an exact-profile registered bulk filed capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCapturePublicResultV1,
    FiledBulkCaptureRequest,
)
from ...application.live.filed_single_capture_operation import FiledReconciliationV1
from ...application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCasillaSkipRow,
    FiledDataCaptureFailureRow,
)
from ...application.modelo.filing_chain_reconciliation import FilingReconciliationResult
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_filed_projection import (
    capture_notice,
    capture_tally_fields,
    reconciliation_result,
    settled_capture_report,
)
from .runtime_profile_binding import require_profile_client
from .runtime_profile_operation import submit_profile_operation


@dataclass(frozen=True, slots=True)
class FiledBulkCaptureRead:
    """Keep the correlated receipt beside the restored presentation report."""

    completion: RegisteredOperationCompletion[FiledBulkCapturePublicResultV1]
    report: BulkFiledDataCaptureReport


def _reconciliation(
    row: FiledReconciliationV1, *, profile_id: UUID, request: FiledBulkCaptureRequest
) -> FilingReconciliationResult:
    if not (request.year_from <= row.filing_year <= request.year_to):
        raise ValueError("filed-bulk reconciliation is outside the submitted scope")
    if request.modelos is not None and row.modelo not in request.modelos:
        raise ValueError("filed-bulk reconciliation has an unrequested modelo")
    return reconciliation_result(row, profile_id=profile_id)


def _presentation_report(
    projection: FiledBulkCapturePublicResultV1, *, profile_id: UUID, request: FiledBulkCaptureRequest
) -> BulkFiledDataCaptureReport:
    """Validate scope and restore canonical report types for CLI rendering."""
    if _bulk_capture_request_differs(projection, request):
        raise ValueError("filed-bulk result does not match its submitted scope")
    _require_bulk_detail_scope(projection, request)
    report = BulkFiledDataCaptureReport(
        output_root=projection.output_root,
        modelos=projection.modelos,
        pair_outcomes=projection.pair_outcomes,
        year_from=projection.year_from,
        year_to=projection.year_to,
        dry_run=projection.dry_run,
        **capture_tally_fields(projection),
        failed_count=projection.failed_count,
        sync_run_ref=projection.sync_run_ref,
        reconciliation_results=tuple(
            _reconciliation(row, profile_id=profile_id, request=request) for row in projection.reconciliations
        ),
        failures=tuple(
            FiledDataCaptureFailureRow(
                modelo=row.modelo,
                year=row.year,
                period=Period.from_year_and_code(row.year, row.period) if row.period is not None else None,
                expediente_id=row.expediente_id,
                error_type=row.error_type,
                message=row.message,
            )
            for row in projection.failures
        ),
        skipped_casillas=tuple(
            FiledCasillaSkipRow(
                modelo=row.modelo,
                year=row.year,
                period=Period.from_year_and_code(row.year, row.period) if row.period is not None else None,
                expediente_id=row.expediente_id,
                casilla_id=row.casilla_id,
                label=row.label,
                value_kind=row.value_kind,
                reason=row.reason,
            )
            for row in projection.skipped_casillas
        ),
        recapture_notices=tuple(capture_notice(row) for row in projection.recapture_notices),
    )

    report.require_consistent()
    return report


def _bulk_capture_effect(report: BulkFiledDataCaptureReport) -> OperationEffect:
    return OperationEffect.UPDATED if report.sync_run_ref is not None else OperationEffect.NONE


def read_filed_bulk_capture_for_cli(
    ctx: typer.Context,
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None,
    limit: int | None,
    dry_run: bool,
) -> FiledBulkCaptureRead:
    """Submit the bulk sweep and accept only its correlated settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledBulkCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
        modelos=modelos,
        limit=limit,
        dry_run=dry_run,
    )
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=FILED_BULK_CAPTURE_DEFINITION_ID,
        result_type=FiledBulkCapturePublicResultV1,
    )
    report = settled_capture_report(
        completed,
        FiledBulkCapturePublicResultV1,
        lambda projection: _presentation_report(projection, profile_id=profile_id, request=request),
        _bulk_capture_effect,
    )
    return FiledBulkCaptureRead(completion=completed, report=report)


__all__ = ["FiledBulkCaptureRead", "read_filed_bulk_capture_for_cli"]


def _bulk_capture_request_differs(projection: FiledBulkCapturePublicResultV1, request: FiledBulkCaptureRequest) -> bool:
    """Require the exact bulk request scope and complete failure count."""
    return (
        projection.output_root != str(request.output_root)
        or projection.year_from != request.year_from
        or projection.year_to != request.year_to
        or (projection.dry_run != request.dry_run)
        or (request.modelos is not None and projection.modelos != request.modelos)
        or (projection.failed_count != len(projection.failures))
    )


def _require_bulk_detail_scope(projection: FiledBulkCapturePublicResultV1, request: FiledBulkCaptureRequest) -> None:
    """Refuse any failure or skipped casilla outside the submitted year and modelo scope."""
    for row in (*projection.failures, *projection.skipped_casillas):
        if not (request.year_from <= row.year <= request.year_to) or (
            request.modelos is not None and row.modelo not in request.modelos
        ):
            raise ValueError("filed-bulk detail row is outside the submitted scope")
