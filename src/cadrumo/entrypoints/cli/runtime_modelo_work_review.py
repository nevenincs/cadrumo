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
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.modelos.work_unit import WorkUnit
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


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
    if _work_review_receipt_invalid(completed, projection, unit, client.profile_id):
        raise invalid_completion_error(completed)
    return ModeloWorkReviewed(completion=completed, review=review)


def _work_review_receipt_invalid(
    completed: RegisteredOperationCompletion[ModeloWorkReviewProjection],
    projection: ModeloWorkReviewProjection,
    unit: WorkUnit,
    profile_id: UUID,
) -> bool:
    """Require the selected work snapshot before accepting the read receipt."""
    return (
        projection.profile_id != profile_id
        or projection.review.bucket_id != unit.bucket_id
        or projection.review.work_unit_id != unit.work_unit_id
        or (projection.review.modelo != str(unit.modelo))
        or (projection.review.filing_year != unit.filing_year)
        or (projection.review.period.to_period() != unit.period)
        or (projection.review.registry_revision_id != unit.revision_id)
        or (completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED)
        or (completed.refusal_code is not None)
        or (completed.effect is not OperationEffect.NONE)
    )
