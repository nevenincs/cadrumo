"""Authenticated CLI bridge for the canonical workstation check report."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import BaseModel

from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.workstation_check_operation import (
    WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
    WorkstationCheckProjection,
    WorkstationCheckRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Refuse a projection that does not match its admitted profile read."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
        _invalid(completed)
    return projection


__all__ = ["read_workstation_check_for_cli"]
