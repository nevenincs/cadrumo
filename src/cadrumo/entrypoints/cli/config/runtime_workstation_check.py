"""Authenticated CLI bridge for the canonical workstation check report."""

from __future__ import annotations

import typer

from ....application.workstation_check_operation import (
    WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
    WorkstationCheckProjection,
    WorkstationCheckRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import run_registered_operation


def read_workstation_check_for_cli(ctx: typer.Context) -> WorkstationCheckProjection:
    """Read and correlate one workstation report through the bound profile worker."""
    client = bound_profile_client(ctx)
    request = WorkstationCheckRequest(profile_id=client.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=WorkstationCheckProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["read_workstation_check_for_cli"]
