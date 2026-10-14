"""CLI transport for a worker-owned, read-only censal preview."""

from __future__ import annotations

import typer

from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_deadlines import provider_login_settlement_seconds
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ....application.user_profile.censal_preview_operation import (
    CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
    CensalPreviewOperationRequest,
    CensalPreviewOperationResult,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .operation_censal_prepare import prepare_censal_review


def preview_censal_operation(ctx: typer.Context) -> CensalPreviewOperationResult:
    """Read and reconcile the bound profile's live census and auth session receipt."""
    client = bound_profile_client(ctx)
    prepared = prepare_censal_review(ctx)
    request = CensalPreviewOperationRequest(
        baseline=prepared.operation_request.baseline,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=CensalPreviewOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        settlement_timeout=provider_login_settlement_seconds(after_login=120),
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["preview_censal_operation"]
