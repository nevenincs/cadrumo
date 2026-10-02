"""Authenticated CLI transport for the cross-domain pipeline report."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.operations.public_period import PublicPeriod
from ...application.overview.pipeline_operation import (
    OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
    OverviewPipelineProjection,
    OverviewPipelineRequest,
)
from ...application.overview.pipeline_projection import PipelineHealthSnapshot
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class OverviewPipelineRead:
    """Keep the exact completed receipt with the worker's compact report."""

    completion: RegisteredOperationCompletion[OverviewPipelineProjection]
    report: PipelineHealthSnapshot


def read_overview_pipeline(
    ctx: typer.Context, *, period: Period, output_language: OutputLanguage
) -> OverviewPipelineRead:
    """Capture one report in the selected profile's authenticated worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    requested_period = PublicPeriod.from_period(period)
    completed = run_registered_operation(
        client,
        OverviewPipelineRequest(
            profile_id=client.profile_id,
            period=requested_period,
            output_language=output_language,
        ),
        definition_id=OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=OverviewPipelineProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    report = projection.report
    if (
        projection.profile_id != client.profile_id
        or projection.period != requested_period
        or projection.output_language is not output_language
        or report.profile_id != client.profile_id
        or report.period != requested_period
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return OverviewPipelineRead(completion=completed, report=report)


__all__ = ["OverviewPipelineRead", "read_overview_pipeline"]
