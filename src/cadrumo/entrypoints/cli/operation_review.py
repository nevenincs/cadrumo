"""Authenticated CLI transport for registered application review reads."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.review.read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewViewReadRequest,
)
from ...application.review.read_projections import (
    ReviewQueueReadProjection,
    ReviewViewReadProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse


def _client(ctx: typer.Context) -> FrontendClient:
    """Return only the invocation client bound to the immutable active profile."""
    return require_profile_client(ctx, expected_profile_id=UUID(active_bucket_id_or_refuse()))


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one typed review request through the exact active-profile client."""
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    client = _client(ctx)
    if client.profile_id != profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )


def _require_success[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    *,
    profile_id: UUID,
    request: BaseModel,
) -> ProjectionT:
    """Correlate the full projection with its exact request and no-effect receipt."""
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or getattr(projection, "profile_id", None) != profile_id
        or getattr(projection, "request", None) != request
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_queue(
    ctx: typer.Context,
    request: ReviewQueueReadRequest,
) -> ReviewQueueReadProjection:
    """Submit the ordered queue filters and return the complete typed read."""
    completed = _submit(
        ctx,
        request,
        definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
        result_type=ReviewQueueReadProjection,
    )
    return _require_success(
        completed,
        profile_id=request.profile_id,
        request=request,
    )


def run_review_view(
    ctx: typer.Context,
    request: ReviewViewReadRequest,
) -> ReviewViewReadProjection:
    """Submit one exact item lookup and return its complete typed row."""
    completed = _submit(
        ctx,
        request,
        definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
        result_type=ReviewViewReadProjection,
    )
    return _require_success(
        completed,
        profile_id=request.profile_id,
        request=request,
    )


__all__ = ["run_review_queue", "run_review_view"]
