"""CLI transport for an authenticated modelo lifecycle history."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.modelo.lifecycle_history_operation import (
    MODELO_HISTORY_OPERATION_DEFINITION_ID,
    ModeloHistoryOperationProjection,
    ModeloHistoryOperationRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse


def read_modelo_history(
    ctx: typer.Context, *, modelo: str, year: int | None, period: str | None
) -> ModeloHistoryOperationProjection:
    """Return only the exact-profile, exact-filter registered history result."""
    expected = UUID(active_bucket_id_or_refuse())
    client = require_profile_client(ctx, expected_profile_id=expected)
    completed = run_registered_operation(
        client,
        ModeloHistoryOperationRequest(profile_id=expected, modelo=modelo, year=year, period=period),
        definition_id=MODELO_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(expected)),
        result_type=ModeloHistoryOperationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or result.profile_id != expected
        or result.modelo != modelo
        or result.year != year
        or result.period != period
    ):
        raise invalid_completion_error(completed)
    return result
