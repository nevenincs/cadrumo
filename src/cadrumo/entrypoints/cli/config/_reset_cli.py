"""CLI transport for durable all-profile configuration reset."""

from __future__ import annotations

import typer

from .._common import emit_envelope
from ..config_payloads import (
    ConfigResetOperationPayload,
    ConfigResetResumeResult,
    ConfigResetStartResult,
    ConfigResetStatusResult,
)
from ..errors import CliRefusedBoundaryError


def _retention_override(
    *,
    enabled: bool,
    reason: str | None,
) -> tuple[bool, str | None]:
    normalized_reason = reason.strip() if reason is not None else None
    if enabled and not normalized_reason:
        raise CliRefusedBoundaryError(
            "config reset retention override requires a non-empty --reason",
            context={"option": "--reason"},
        )
    if not enabled and normalized_reason:
        raise CliRefusedBoundaryError(
            "config reset --reason is valid only with --override-retention",
            context={"option": "--override-retention"},
        )
    return enabled, normalized_reason


def _require_yes_and_override(
    yes: bool,
    override_retention: bool,
    reason: str | None,
) -> tuple[bool, str | None]:
    """Refuse without ``--yes``, then validate the retention-override pairing."""
    if not yes:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.reset.requires_yes",
        )
    return _retention_override(enabled=override_retention, reason=reason)


def _operation_lines(operation: ConfigResetOperationPayload) -> tuple[str, ...]:
    lines = [
        f"operation_id\t{operation.operation_id}",
        f"status\t{operation.status}",
        f"started_at\t{operation.started_at}",
        f"updated_at\t{operation.updated_at}",
        f"targets\t{len(operation.targets)}",
        f"pause_reason\t{operation.pause_reason or ''}",
    ]
    lines.extend(
        (
            f"target\t{target.bucket_id}\t{target.phase}\t"
            f"retention_override={str(bool(target.retention_override_approved)).lower()}"
        )
        for target in operation.targets
    )
    if operation.summary is not None:
        lines.extend(
            (
                f"deleted\t{operation.summary.deleted_count}",
                f"already_absent\t{operation.summary.already_absent_count}",
                f"retention_overrides\t{operation.summary.retention_override_count}",
                f"completed_at\t{operation.summary.completed_at}",
            ),
        )
    return tuple(lines)


def config_reset_start(
    ctx: typer.Context,
    yes: bool = False,
    override_retention: bool = False,
    reason: str | None = None,
) -> None:
    """Start and execute one new reset operation."""
    override_retention, reason = _require_yes_and_override(yes, override_retention, reason)
    from ....application.config_reset import start_config_reset

    operation = start_config_reset(
        confirmed=True,
        acknowledge_retention_override=override_retention,
        retention_override_reason=reason,
    )
    projection = ConfigResetOperationPayload.from_operation(operation)
    emit_envelope(
        ctx,
        command="config.reset.start",
        result=ConfigResetStartResult(operation=projection),
        lines=_operation_lines(projection),
    )


def config_reset_status_command(
    ctx: typer.Context,
    operation_id: str | None = None,
) -> None:
    """Read one reset journal without resuming it."""
    from ....application.config_reset import config_reset_status

    operation = config_reset_status(operation_id)
    projection = ConfigResetOperationPayload.from_operation(operation) if operation is not None else None
    emit_envelope(
        ctx,
        command="config.reset.status",
        result=ConfigResetStatusResult(operation=projection),
        lines=(_operation_lines(projection) if projection is not None else ("operation\t<none>",)),
    )


def config_reset_resume(
    ctx: typer.Context,
    operation_id: str | None = None,
    yes: bool = False,
    override_retention: bool = False,
    reason: str | None = None,
) -> None:
    """Roll one exact incomplete journal forward."""
    override_retention, reason = _require_yes_and_override(yes, override_retention, reason)
    from ....application.config_reset import (
        config_reset_status,
        resume_config_reset,
    )

    resolved_operation_id = operation_id
    if resolved_operation_id is None:
        candidate = config_reset_status()
        if candidate is None or candidate.status.value == "complete":
            raise CliRefusedBoundaryError(
                "no incomplete configuration reset operation is available to resume",
            )
        resolved_operation_id = candidate.operation_id
    operation = resume_config_reset(
        resolved_operation_id,
        confirmed=True,
        acknowledge_retention_override=override_retention,
        retention_override_reason=reason,
    )
    projection = ConfigResetOperationPayload.from_operation(operation)
    emit_envelope(
        ctx,
        command="config.reset.resume",
        result=ConfigResetResumeResult(operation=projection),
        lines=_operation_lines(projection),
    )


__all__ = ["config_reset_resume", "config_reset_start", "config_reset_status_command"]
