"""CLI transport for one authenticated compact work-review snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.modelo.work_review_operation import (
    MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
    ModeloWorkReviewProjection,
    ModeloWorkReviewRequest,
    ModeloWorkReviewSnapshot,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.modelos.work_unit import WorkUnit
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloWorkReviewed:
    """Keep the exact worker receipt with its correlated review snapshot."""

    completion: RegisteredOperationCompletion[ModeloWorkReviewProjection]
    review: ModeloWorkReviewSnapshot


def read_modelo_work_review(ctx: typer.Context, *, unit: WorkUnit) -> ModeloWorkReviewed:
    """Return only the review matching the already authenticated unit snapshot."""
    client = require_profile_client(ctx, expected_profile_id=UUID(unit.bucket_id))
    completed = run_registered_operation(
        client,
        ModeloWorkReviewRequest(profile_id=client.profile_id, work_unit_id=unit.work_unit_id),
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        result_type=ModeloWorkReviewProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    review = projection.review
    if (
        projection.profile_id != client.profile_id
        or review.bucket_id != unit.bucket_id
        or review.work_unit_id != unit.work_unit_id
        or review.modelo != str(unit.modelo)
        or review.filing_year != unit.filing_year
        or review.period.to_period() != unit.period
        or review.registry_revision_id != unit.revision_id
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
    return ModeloWorkReviewed(completion=completed, review=review)
