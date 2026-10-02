"""Authenticated CLI bridge for worker-owned application diagnostics."""

from __future__ import annotations

from datetime import date
from typing import Literal, Never

import typer
from pydantic import BaseModel, ValidationError

from ...application.diagnostics_operation import (
    DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
    DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
    DiagnosticsTelemetryFlushProjection,
    DiagnosticsTelemetryFlushRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.telemetry.tier import TelemetryTier
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)

DiagnosticsReadKind = Literal["run_health", "runs", "latency", "errors", "llm_usage"]
_RESULT_FIELDS = ("run_health", "runs", "latency", "errors", "llm_usage")


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Refuse a result or effect that does not match its registered receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.kind != request.kind
        or projection.since != request.since
        or projection.until != request.until
        or projection.provider != request.provider
        or projection.limit != request.limit
        or selected != (kind,)
    ):
        _invalid(completed)
    return projection


def flush_diagnostics_telemetry(
    ctx: typer.Context,
    *,
    dry_run: bool,
    acknowledged: bool,
    opt_in: bool | None,
    tier: TelemetryTier | None,
    endpoint: str | None,
) -> DiagnosticsTelemetryFlushProjection:
    """Preview or send telemetry through the exact profile's registered worker."""
    client = bound_profile_client(ctx)
    try:
        request = DiagnosticsTelemetryFlushRequest(
            profile_id=client.profile_id,
            dry_run=dry_run,
            acknowledged=acknowledged,
            opt_in=opt_in,
            tier=tier,
            endpoint=endpoint,
        )
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    completed = run_registered_operation(
        client,
        request,
        definition_id=DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=DiagnosticsTelemetryFlushProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    expected_effect = OperationEffect.UNKNOWN if projection.sent else OperationEffect.NONE
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.dry_run != request.dry_run
        or (request.dry_run and projection.sent)
    ):
        _invalid(completed)
    return projection


__all__ = ["DiagnosticsReadKind", "flush_diagnostics_telemetry", "read_diagnostics"]
