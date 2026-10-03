"""Authenticated CLI transport bridge for the prorrata register operations."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.prorrata_register.operation_requests import PRORRATA_LIST_OPERATION_DEFINITION_ID
from ...application.prorrata_register.projection_contracts import (
    ProrrataListProjection,
    ProrrataMutationProjection,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context, profile_id: UUID) -> RuntimeFrontendClient:
    """Return only the invocation client bound to the current immutable profile."""
    expected_profile_id = UUID(active_bucket_id_or_refuse())
    if profile_id != expected_profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return require_profile_client(ctx, expected_profile_id=expected_profile_id)


def submit_prorrata_operation[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    mutation: bool,
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one exact-profile prorrata request through the shared runtime."""
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeError("prorrata request has no typed profile identity")
    client = _client(ctx, profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=mutation,
    )
    projection_profile_id = getattr(completed.projection, "profile_id", None)
    if projection_profile_id != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def validate_prorrata_list_completion(
    completed: RegisteredOperationCompletion[ProrrataListProjection],
) -> ProrrataListProjection:
    """Verify list payload and its terminal receipt agree before disclosure."""
    if (
        completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and completed.effect is OperationEffect.NONE
        and completed.refusal_code is None
    ):
        return completed.projection
    raise invalid_completion_error(completed)


def validate_prorrata_mutation_completion(
    completed: RegisteredOperationCompletion[ProrrataMutationProjection],
    *,
    operation_id: str,
) -> ProrrataMutationProjection:
    """Verify mutation or refusal projection against the settled effect receipt."""
    projection = completed.projection
    refused = projection.outcome == "refused"
    refusal = projection.refusal
    if (
        projection.operation_id != operation_id
        or completed.terminal_condition
        is not (OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED)
        or completed.effect is not (OperationEffect.NONE if refused else OperationEffect.UPDATED)
        or completed.refusal_code != (refusal.code if refusal is not None else None)
    ):
        raise invalid_completion_error(completed)
    return projection


def submit_prorrata_list(
    ctx: typer.Context,
    request: BaseModel,
) -> RegisteredOperationCompletion[ProrrataListProjection]:
    """Submit the all-period list operation and project it as ``ProrrataListProjection``."""
    return submit_prorrata_operation(
        ctx,
        request,
        definition_id=PRORRATA_LIST_OPERATION_DEFINITION_ID,
        result_type=ProrrataListProjection,
        mutation=False,
    )


def submit_prorrata_mutation(
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
) -> RegisteredOperationCompletion[ProrrataMutationProjection]:
    """Submit one registered prorrata mutation with declared refusal details."""
    return submit_prorrata_operation(
        ctx,
        request,
        definition_id=definition_id,
        result_type=ProrrataMutationProjection,
        mutation=True,
    )


__all__ = [
    "submit_prorrata_list",
    "submit_prorrata_mutation",
    "validate_prorrata_list_completion",
    "validate_prorrata_mutation_completion",
]
