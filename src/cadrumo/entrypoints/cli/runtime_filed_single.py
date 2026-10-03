"""CLI bridge for one exact-profile registered filed capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledReconciliationV1,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
)
from ...application.live.remote_state_models import FiledDataCaptureReport
from ...application.modelo.filing_chain_reconciliation import FilingReconciliationResult
from ...core.bucket_pointer import require_active_bucket_id
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_filed_projection import (
    capture_evidence_effect,
    capture_tally_fields,
    reconciliation_result,
    settled_capture_report,
)
from .runtime_profile_binding import require_profile_client
from .runtime_profile_operation import submit_profile_operation


@dataclass(frozen=True, slots=True)
class FiledSingleCaptureRead:
    """Keep the settled worker receipt with the restored CLI report."""

    completion: RegisteredOperationCompletion[FiledSingleCapturePublicResultV1]
    report: FiledDataCaptureReport


def _reconciliation(
    row: FiledReconciliationV1,
    *,
    profile_id: UUID,
    request: FiledSingleCaptureRequest,
) -> FilingReconciliationResult:
    if row.modelo != request.modelo or row.filing_year != request.year:
        raise ValueError("filed-capture reconciliation does not match its profile pair")
    result = reconciliation_result(row, profile_id=profile_id)
    if request.period is not None and result.period != Period.from_year_and_code(request.year, request.period):
        raise ValueError("filed-capture reconciliation does not match its requested period")
    return result


def _presentation_report(
    projection: FiledSingleCapturePublicResultV1,
    *,
    profile_id: UUID,
    request: FiledSingleCaptureRequest,
) -> FiledDataCaptureReport:
    """Restore the existing renderer report from its safe public projection."""
    if (
        projection.output_root != str(request.output_root)
        or projection.modelo != request.modelo
        or projection.year != request.year
    ):
        raise ValueError("filed-capture result does not match its submitted pair")
    reconciliations = tuple(
        _reconciliation(row, profile_id=profile_id, request=request) for row in projection.reconciliations
    )
    return FiledDataCaptureReport(
        output_root=projection.output_root,
        modelo=projection.modelo,
        year=projection.year,
        **capture_tally_fields(projection),
        reconciliation_results=reconciliations,
    )


def read_filed_single_capture_for_cli(
    ctx: typer.Context,
    *,
    modelo: str,
    year: int,
    output_root: Path,
    period: Period | None,
    expediente_id: str | None,
    limit: int | None,
) -> FiledSingleCaptureRead:
    """Submit one capture and accept only its exact-profile settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledSingleCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        modelo=modelo,
        year=year,
        period=period.registry_token if period is not None else None,
        expediente_id=expediente_id,
        limit=limit,
    )
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=FILED_SINGLE_CAPTURE_DEFINITION_ID,
        result_type=FiledSingleCapturePublicResultV1,
    )
    report = settled_capture_report(
        completed,
        FiledSingleCapturePublicResultV1,
        lambda projection: _presentation_report(projection, profile_id=profile_id, request=request),
        capture_evidence_effect,
    )
    return FiledSingleCaptureRead(completion=completed, report=report)


__all__ = ["FiledSingleCaptureRead", "read_filed_single_capture_for_cli"]
