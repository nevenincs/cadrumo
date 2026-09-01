"""Profile repair behavior handlers for ``aeat config repair``.

Reads the active :class:`UserProfileRecord` through the injected record reader
to diagnose and repair the bucket-backed profile state.
"""

from __future__ import annotations

import typing
from collections.abc import Callable

import typer

from ....core.bucket_pointer import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.errors.hierarchy import CadrumoError as _CadrumoError
from ....core.redaction.rules import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    redact_structured_for_cli_output,
)
from .._common import emit_envelope, resolve_cli_precondition_action
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from .errors import ConfigBoundaryError as _ConfigBoundaryError
from .status_rendering import precondition_action_lines

if typing.TYPE_CHECKING:
    from ....application.workflow.profile_bucket_models import ProfileBucketPointer
    from ....application.workflow.profile_health import ActiveProfileHealth
    from ....domain.user_profile.values import UserProfileRecord


ProfileResolver = Callable[[str], "ProfileBucketPointer"]
ProfileRecordReader = Callable[..., "UserProfileRecord"]


def repair_profile(
    ctx: typer.Context,
    profile: str | None = None,
    clear_active: bool = False,
    yes: bool = False,
) -> None:
    """Inspect profile health or safely repair a degraded active-profile pointer."""
    from ._profile_readiness import _read_profile_record as read_profile_record
    from ._profile_support import resolve_profile_by_label

    if profile is not None and not clear_active:
        _emit_profile_record_status(
            ctx,
            profile,
            resolve_profile_by_label=resolve_profile_by_label,
            read_profile_record=read_profile_record,
        )
        return
    _validate_repair_action_preconditions(
        profile=profile,
        clear_active=clear_active,
        yes=yes,
        resolve_profile_by_label=resolve_profile_by_label,
    )
    _emit_pointer_repair(ctx, clear_active=clear_active, confirmed=yes)


def _validate_repair_action_preconditions(
    *,
    profile: str | None,
    clear_active: bool,
    yes: bool,
    resolve_profile_by_label: ProfileResolver,
) -> None:
    """Refuse mutually-exclusive, mismatched, or unconfirmed repair actions.

    Raises :class:`CliRefusedBoundaryError` when ``--profile`` names a
    non-active bucket for pointer repair, or when a destructive action lacks
    ``--yes``.
    """
    if profile is not None:
        resolved = resolve_profile_by_label(profile)
        if resolved.bucket_id != _resolve_active_bucket_id():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.repair.profile_clear_active_mismatch",
                context={"profile": profile},
            )
    if clear_active and not yes:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.profile_requires_yes",
        )


def _emit_pointer_repair(ctx: typer.Context, *, clear_active: bool, confirmed: bool) -> None:
    """Repair a degraded active-profile pointer and emit the health result."""
    from ....application.workflow.profile_health import repair_active_profile_pointer
    from .._config_payloads import RepairProfileResult

    result = repair_active_profile_pointer(clear_active=clear_active, confirmed=confirmed)
    health = result.after or result.before
    active_profile = _repair_profile_label(health)
    payload = {
        "dry_run": result.dry_run,
        "cleared_pointer": result.cleared_pointer,
        "before": _profile_health_payload(result.before),
        "after": _profile_health_payload(result.after) if result.after is not None else None,
    }
    payload = _redact_profile_repair_payload(payload)
    lines = [
        f"dry_run\t{result.dry_run}",
        f"cleared_pointer\t{result.cleared_pointer}",
        f"active_profile\t{active_profile or ''}",
        f"source\t{health.source}",
        f"status\t{health.status}",
        f"registered_bucket\t{health.registered_bucket}",
        f"profile_record_present\t{health.profile_record_present}",
        f"repairable_by_clearing_pointer\t{health.repairable_by_clearing_pointer}",
    ]
    if health.profile_record_error:
        lines.append(f"profile_record_error\t{health.profile_record_error}")
    repair_payload = RepairProfileResult.model_validate(payload)
    health_payload = repair_payload.after or repair_payload.before
    if health_payload is not None:
        lines.extend(precondition_action_lines(health_payload.precondition_action))
    emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)


def _profile_health_payload(health: ActiveProfileHealth) -> dict[str, object]:
    """Project one health verdict through the canonical CLI action resolver."""
    dumped = health.model_dump(mode="json", exclude={"precondition_verdict"})
    if not isinstance(dumped, dict):
        raise TypeError("profile health payload must be a mapping")
    payload: dict[str, object] = {}
    for key, value in dumped.items():
        if not isinstance(key, str):
            raise TypeError("profile health payload keys must be text")
        payload[key] = value
    payload["active_profile"] = _repair_profile_label(health)
    if health.precondition_verdict is not None:
        action = resolve_cli_precondition_action(health.precondition_verdict)
        payload["precondition_action"] = action
    return payload


def _repair_profile_label(health: ActiveProfileHealth) -> str | None:
    """Project a manifest label while keeping an unresolved bucket id private."""
    if health.active_profile_label:
        return health.active_profile_label
    if health.active_profile:
        return CLI_PROFILE_ID_PLACEHOLDER
    return None


# The repair envelope carries a heterogeneous operator-facing payload (strings,
# bools, nested health records). Naming a concrete value type here would either
# exclude a field the envelope legitimately carries or restate the envelope's
# shape from a second place; the redaction contract governs the values.
# ANY-RETURN-RATIONALE-REPAIR-PAYLOAD-REDACTION: pass-through to the redaction funnel.
def _redact_profile_repair_payload(payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Return a paste-safe repair payload with internal profile ids removed."""
    redacted = redact_structured_for_cli_output(payload)
    if not isinstance(redacted, dict):
        return {}
    return {str(k): v for k, v in redacted.items()}


def _emit_profile_record_status(
    ctx: typer.Context,
    label: str,
    *,
    resolve_profile_by_label: ProfileResolver,
    read_profile_record: ProfileRecordReader,
) -> None:
    """Emit a non-secret status report for one registered profile bucket."""
    from ....application.workflow.profile_health import unavailable_profile_record_verdict
    from ....domain.user_profile.errors import ProfileNotFoundError
    from .._config_payloads import RepairProfileResult

    pointer = resolve_profile_by_label(label)
    profile_id = pointer.bucket_id
    try:
        record = read_profile_record(profile_id=profile_id, bucket_id=profile_id)
    except ProfileNotFoundError:
        payload = {
            "profile_id": profile_id,
            "bucket_id": profile_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "missing_profile_record",
            "precondition_action": resolve_cli_precondition_action(
                unavailable_profile_record_verdict(
                    status="missing_profile_record",
                    source="none",
                    repairable_by_clearing_pointer=False,
                )
            ),
        }
        repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
        emit_envelope(
            ctx,
            command="config.repair.profile",
            result=repair_payload,
            lines=(
                "readiness\tmissing_profile_record",
                f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
                f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tmissing",
                *precondition_action_lines(repair_payload.precondition_action),
            ),
        )
        raise typer.Exit(code=2) from None
    except _CadrumoError as exc:
        _emit_profile_record_unreadable_repair(
            ctx,
            pointer=pointer,
            profile_id=profile_id,
            error=exc,
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        from ....core.logging import get_logger

        get_logger(__name__).debug("config repair profile wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable_repair(
            ctx,
            pointer=pointer,
            profile_id=profile_id,
            error=exc,
        )
        raise typer.Exit(code=2) from boundary
    payload = {
        "profile_id": profile_id,
        "bucket_id": profile_id,
        "display_name": pointer.label,
        "registered_bucket": True,
        "profile_record_present": True,
        "setup_state": record.setup_state,
    }
    repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
    emit_envelope(
        ctx,
        command="config.repair.profile",
        result=repair_payload,
        lines=(
            "readiness\tready",
            f"display_name\t{pointer.label}",
            f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
            f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
            "registered_bucket\tpresent",
            "profile_record\tpresent",
            f"setup_state\t{record.setup_state.value}",
        ),
    )


def _emit_profile_record_unreadable_repair(
    ctx: typer.Context,
    *,
    pointer: ProfileBucketPointer,
    profile_id: str,
    error: Exception,
) -> None:
    from ....application.workflow.profile_health import unavailable_profile_record_verdict
    from .._config_payloads import RepairProfileResult

    payload = {
        "profile_id": profile_id,
        "bucket_id": profile_id,
        "display_name": pointer.label,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": type(error).__name__,
        "precondition_action": resolve_cli_precondition_action(
            unavailable_profile_record_verdict(
                status="profile_record_unreadable",
                source="none",
                repairable_by_clearing_pointer=False,
            )
        ),
    }
    repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
    emit_envelope(
        ctx,
        command="config.repair.profile",
        result=repair_payload,
        lines=(
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
            f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
            f"display_name\t{pointer.label}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            *precondition_action_lines(repair_payload.precondition_action),
        ),
    )


__all__ = ["repair_profile"]
