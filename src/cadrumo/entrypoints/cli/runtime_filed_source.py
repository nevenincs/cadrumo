"""CLI bridge for one exact-profile registered filed source capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_source_capture_operation import (
    FILED_SOURCE_CAPTURE_DEFINITION_ID,
    FiledSourceCapturePublicResultV1,
    FiledSourceCaptureRequest,
)
from ...application.live.remote_state_models import SourceFiledDataCaptureReport
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
class FiledSourceCaptureRead:
    """Keep the settled worker receipt with the restored CLI report."""

    completion: RegisteredOperationCompletion[FiledSourceCapturePublicResultV1]
    report: SourceFiledDataCaptureReport


def _presentation_report(
    projection: FiledSourceCapturePublicResultV1,
    *,
    profile_id: UUID,
    request: FiledSourceCaptureRequest,
) -> SourceFiledDataCaptureReport:
    """Restore the current renderer report from its safe public projection."""
    target_period = Period.from_year_and_code(projection.target_year, projection.target_period)
    requested_period = Period.from_year_and_code(request.year, request.period)
    if (
        projection.output_root != str(request.output_root)
        or projection.target_modelo != request.modelo
        or projection.target_year != request.year
        or target_period != requested_period
    ):
        raise ValueError("filed-source result does not match its submitted target")
    reconciliations = tuple(reconciliation_result(row, profile_id=profile_id) for row in projection.reconciliations)
    return SourceFiledDataCaptureReport(
        output_root=projection.output_root,
        target_modelo=projection.target_modelo,
        target_year=projection.target_year,
        target_period=target_period,
        **capture_tally_fields(projection),
        reconciliation_results=reconciliations,
    )


def read_filed_source_capture_for_cli(
    ctx: typer.Context,
    *,
    modelo: str,
    year: int,
    period: Period,
    output_root: Path,
) -> FiledSourceCaptureRead:
    """Submit one source capture and accept only its exact-profile settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledSourceCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        modelo=modelo,
        year=year,
        period=period.registry_token,
    )
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=FILED_SOURCE_CAPTURE_DEFINITION_ID,
        result_type=FiledSourceCapturePublicResultV1,
    )
    report = settled_capture_report(
        completed,
        FiledSourceCapturePublicResultV1,
        lambda projection: _presentation_report(projection, profile_id=profile_id, request=request),
        capture_evidence_effect,
    )
    return FiledSourceCaptureRead(completion=completed, report=report)


__all__ = ["FiledSourceCaptureRead", "read_filed_source_capture_for_cli"]
