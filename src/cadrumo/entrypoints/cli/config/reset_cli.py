"""CLI transport for durable all-profile configuration reset."""

from __future__ import annotations

from uuid import uuid4

import typer

from ....application.config_reset_documents import ConfigResetOperationPayload
from ..common import emit_envelope
from ..config_payloads import (
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
    from ....application.config_reset import (
        ConfigResetRequestProblem,
        ConfigResetRequestRefusedError,
        normalise_retention_override,
    )

    try:
        override = normalise_retention_override(
            acknowledge_retention_override=enabled,
            retention_override_reason=reason,
        )
    except ConfigResetRequestRefusedError as refusal:
        if refusal.problem is ConfigResetRequestProblem.OVERRIDE_REASON_REQUIRED:
            raise CliRefusedBoundaryError(
                "config reset retention override requires a non-empty --reason",
                context={"option": "--reason"},
            ) from refusal
        raise CliRefusedBoundaryError(
            "config reset --reason is valid only with --override-retention",
            context={"option": "--override-retention"},
        ) from refusal
    return override.acknowledged, override.reason


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
    """Start and execute one new reset operation.

    A running runtime hosts profile workers that hold the stores a reset
    deletes, so when one answers the reset is its act, which drains them first.
    With no runtime the reset runs in this process.
    """
    override_retention, reason = _require_yes_and_override(yes, override_retention, reason)
    from ....application.operations.registry import OperationFrontendProjection
    from ....application.runtime.installation_requests import RuntimeResetStartReply, RuntimeResetStartRequest
    from ..runtime_installation import run_installation_act_if_runtime

    reply = run_installation_act_if_runtime(
        RuntimeResetStartRequest(
            request_id=uuid4(),
            frontend=OperationFrontendProjection.CLI,
            confirmed=True,
            acknowledge_retention_override=override_retention,
            retention_override_reason=reason,
        ),
        RuntimeResetStartReply,
    )
    if reply is not None:
        projection = reply.operation
    else:
        from ....application.config_reset import start_config_reset
        from ..state_projection_support import bucket_storage, certificate_secret_backend_factory, operator_scope_ports

        projection = ConfigResetOperationPayload.from_operation(
            start_config_reset(
                certificate_secret_backend_factory=certificate_secret_backend_factory(ctx),
                operator_scope_ports=operator_scope_ports(ctx),
                bucket_storage=bucket_storage(ctx),
                confirmed=True,
                acknowledge_retention_override=override_retention,
                retention_override_reason=reason,
            )
        )
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
    """Roll one exact incomplete journal forward, through the running runtime when there is one."""
    override_retention, reason = _require_yes_and_override(yes, override_retention, reason)
    from ....application.config_reset import ConfigResetRequestRefusedError, latest_incomplete_config_reset_id
    from ....application.operations.registry import OperationFrontendProjection
    from ....application.runtime.installation_requests import RuntimeResetResumeReply, RuntimeResetResumeRequest
    from ..runtime_installation import run_installation_act_if_runtime

    resolved_operation_id = operation_id
    if resolved_operation_id is None:
        try:
            resolved_operation_id = latest_incomplete_config_reset_id()
        except ConfigResetRequestRefusedError as refusal:
            raise CliRefusedBoundaryError(
                "no incomplete configuration reset operation is available to resume",
            ) from refusal
    reply = run_installation_act_if_runtime(
        RuntimeResetResumeRequest(
            request_id=uuid4(),
            frontend=OperationFrontendProjection.CLI,
            operation_id=resolved_operation_id,
            confirmed=True,
            acknowledge_retention_override=override_retention,
            retention_override_reason=reason,
        ),
        RuntimeResetResumeReply,
    )
    if reply is not None:
        projection = reply.operation
    else:
        from ....application.config_reset import resume_config_reset
        from ..state_projection_support import bucket_storage, certificate_secret_backend_factory, operator_scope_ports

        projection = ConfigResetOperationPayload.from_operation(
            resume_config_reset(
                resolved_operation_id,
                certificate_secret_backend_factory=certificate_secret_backend_factory(ctx),
                operator_scope_ports=operator_scope_ports(ctx),
                bucket_storage=bucket_storage(ctx),
                confirmed=True,
                acknowledge_retention_override=override_retention,
                retention_override_reason=reason,
            )
        )
    emit_envelope(
        ctx,
        command="config.reset.resume",
        result=ConfigResetResumeResult(operation=projection),
        lines=_operation_lines(projection),
    )


__all__ = ["config_reset_resume", "config_reset_start", "config_reset_status_command"]
