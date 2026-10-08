"""Authenticated CLI bridge for worker-owned application diagnostics."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.diagnostics_operation import DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
from ...application.diagnostics_read_contracts import (
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation

DiagnosticsReadKind = Literal["run_health", "runs", "latency", "errors", "llm_usage"]
_RESULT_FIELDS = ("run_health", "runs", "latency", "errors", "llm_usage")


def read_diagnostics(
    ctx: typer.Context,
    *,
    kind: DiagnosticsReadKind,
    since: date | None,
    until: date | None,
    provider: str | None,
    limit: int | None = None,
) -> DiagnosticsReadProjection:
    """Read one exact-profile diagnostic report through the registered worker."""
    client = bound_profile_client(ctx)
    try:
        request = DiagnosticsReadRequest(
            profile_id=client.profile_id,
            kind=kind,
            since=since,
            until=until,
            provider=provider,
            limit=limit,
        )
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    completed = run_registered_operation(
        client,
        request,
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=DiagnosticsReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    selected = tuple(name for name in _RESULT_FIELDS if getattr(projection, name) is not None)
    if _diagnostics_read_receipt_invalid(completed, projection, client.profile_id, request, selected, kind):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["DiagnosticsReadKind", "read_diagnostics"]


def _diagnostics_read_receipt_invalid(
    completed: RegisteredOperationCompletion[DiagnosticsReadProjection],
    projection: DiagnosticsReadProjection,
    profile_id: UUID,
    request: DiagnosticsReadRequest,
    selected: tuple[str, ...],
    kind: DiagnosticsReadKind,
) -> bool:
    """Require the settled read, exact request fields, and its sole selected result arm."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or (projection.profile_id != profile_id)
        or (projection.kind != request.kind)
        or (projection.since != request.since)
        or (projection.until != request.until)
        or (projection.provider != request.provider)
        or (projection.limit != request.limit)
        or (selected != (kind,))
    )
