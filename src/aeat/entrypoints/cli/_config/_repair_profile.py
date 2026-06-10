"""Profile repair command registration for ``aeat config repair``.

Reads the active :class:`UserProfileRecord` through the injected record reader
to diagnose and repair the bucket-backed profile state.
"""

from __future__ import annotations

import typing
from collections.abc import Callable

import typer

from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.errors import AeatError as _AeatError
from ....core.i18n import tr
from ....core.redaction import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    redact_structured_for_cli_output,
)
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._errors import ConfigBoundaryError as _ConfigBoundaryError

if typing.TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer
    from ....domain.user_profile import UserProfileRecord


ProfileResolver = Callable[[str], "ProfileBucketPointer"]
ProfileRecordReader = Callable[..., "UserProfileRecord"]


def register_repair_profile_command(
    repair_app: typer.Typer,
    *,
    resolve_profile_by_label: ProfileResolver,
    read_profile_record: ProfileRecordReader,
) -> None:
    """Register profile repair and health commands."""

    @repair_app.command(
        "profile",
        help=tr("cli.config.repair.profile_help"),
    )
    def repair_profile(
        ctx: typer.Context,
        profile: str | None = typer.Option(
            None,
            "--profile",
            help=tr("cli.config.repair.profile_name_help"),
        ),
        clear_active: bool = typer.Option(
            False,
            "--clear-active",
            help=tr("cli.config.repair.profile_clear_active_help"),
        ),
        repair_manifest_status: bool = typer.Option(
            False,
            "--repair-manifest-status",
            help=tr(
                "cli.config.repair.profile_repair_manifest_status_help",
                default="Backfill a legacy active bucket manifest status from the encrypted profile record.",
            ),
        ),
        yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.yes_help")),
    ) -> None:
        """Inspect profile health or safely repair a degraded active-profile pointer/manifest."""
        if profile is not None and not clear_active and not repair_manifest_status:
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
            repair_manifest_status=repair_manifest_status,
            yes=yes,
            resolve_profile_by_label=resolve_profile_by_label,
        )
        if repair_manifest_status:
            _emit_manifest_status_repair(ctx, confirmed=yes)
            return
        _emit_pointer_repair(ctx, clear_active=clear_active, confirmed=yes)


def _validate_repair_action_preconditions(
    *,
    profile: str | None,
    clear_active: bool,
    repair_manifest_status: bool,
    yes: bool,
    resolve_profile_by_label: ProfileResolver,
) -> None:
    """Refuse mutually-exclusive, mismatched, or unconfirmed repair actions.

    Raises :class:`CliRefusedBoundaryError` when both repair actions are
    requested at once, when ``--profile`` names a non-active bucket for a
    pointer/manifest repair, or when a destructive action lacks ``--yes``.
    """
    if clear_active and repair_manifest_status:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.profile_one_action",
        )
    if profile is not None:
        resolved = resolve_profile_by_label(profile)
        if resolved.bucket_id != _resolve_active_bucket_id():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.repair.profile_clear_active_mismatch",
                context={"profile": profile},
            )
    if (clear_active or repair_manifest_status) and not yes:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.profile_requires_yes",
        )


def _emit_manifest_status_repair(ctx: typer.Context, *, confirmed: bool) -> None:
    """Backfill a legacy active-bucket manifest status and emit the result."""
    from ....application.workflow import repair_active_profile_manifest_status
    from .._config_payloads import RepairProfileResult

    result = repair_active_profile_manifest_status(confirmed=confirmed)
    health = result.after or result.before
    lines = [
        f"dry_run\t{result.dry_run}",
        f"repaired\t{result.repaired}",
        f"active_profile\t{CLI_PROFILE_ID_PLACEHOLDER if health.active_profile else ''}",
        f"status\t{health.status}",
        f"manifest_status\t{result.status or ''}",
        f"reason\t{result.reason}",
    ]
    if health.profile_record_error:
        lines.append(f"profile_record_error\t{health.profile_record_error}")
    if health.next_action:
        lines.append(f"next_action\t{health.next_action}")
    repair_payload = RepairProfileResult.model_validate(_redact_profile_repair_payload(result.model_dump(mode="json")))
    _emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)


def _emit_pointer_repair(ctx: typer.Context, *, clear_active: bool, confirmed: bool) -> None:
    """Repair a degraded active-profile pointer and emit the health result."""
    from ....application.workflow import repair_active_profile_pointer
    from .._config_payloads import RepairProfileResult

    result = repair_active_profile_pointer(clear_active=clear_active, confirmed=confirmed)
    health = result.after or result.before
    payload = _redact_profile_repair_payload(result.model_dump(mode="json"))
    lines = [
        f"dry_run\t{result.dry_run}",
        f"cleared_pointer\t{result.cleared_pointer}",
        f"active_profile\t{CLI_PROFILE_ID_PLACEHOLDER if health.active_profile else ''}",
        f"source\t{health.source}",
        f"status\t{health.status}",
        f"registered_bucket\t{health.registered_bucket}",
        f"profile_record_present\t{health.profile_record_present}",
        f"repairable_by_clearing_pointer\t{health.repairable_by_clearing_pointer}",
    ]
    if health.profile_record_error:
        lines.append(f"profile_record_error\t{health.profile_record_error}")
    if health.next_action:
        lines.append(f"next_action\t{health.next_action}")
    repair_payload = RepairProfileResult.model_validate(payload)
    _emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)


def _redact_profile_repair_payload(payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Return a paste-safe repair payload with internal profile ids removed."""
    redacted = redact_structured_for_cli_output(payload)
    if not isinstance(redacted, dict):
        return {}
    return {str(k): v for k, v in redacted.items()}


def profile_record_missing_next_action(profile_id: str, *, label: str) -> str:
    """Return the operator command for repairing a missing profile record."""
    if profile_id == _resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


def profile_record_unreadable_next_action(profile_id: str, *, label: str) -> str:
    """Return the operator command for repairing an unreadable profile record."""
    if profile_id == _resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


def _emit_profile_record_status(
    ctx: typer.Context,
    label: str,
    *,
    resolve_profile_by_label: ProfileResolver,
    read_profile_record: ProfileRecordReader,
) -> None:
    """Emit a non-secret status report for one registered profile bucket."""
    from ....domain.user_profile import ProfileNotFoundError
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
            "next_action": profile_record_missing_next_action(profile_id, label=pointer.label),
        }
        repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
        _emit_envelope(
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
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from None
    except _AeatError as exc:
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
        "display_name": record.display_name,
        "registered_bucket": True,
        "profile_record_present": True,
        "status": record.status.value,
        "next_action": f"aeat config unlock {pointer.label}",
    }
    repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
    _emit_envelope(
        ctx,
        command="config.repair.profile",
        result=repair_payload,
        lines=(
            "readiness\tready",
            f"display_name\t{record.display_name}",
            f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
            f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
            "registered_bucket\tpresent",
            "profile_record\tpresent",
            f"status\t{record.status.value}",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _emit_profile_record_unreadable_repair(
    ctx: typer.Context,
    *,
    pointer: ProfileBucketPointer,
    profile_id: str,
    error: Exception,
) -> None:
    from .._config_payloads import RepairProfileResult

    payload = {
        "profile_id": profile_id,
        "bucket_id": profile_id,
        "display_name": pointer.label,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else type(error).__name__}",
        "next_action": profile_record_unreadable_next_action(profile_id, label=pointer.label),
    }
    repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
    _emit_envelope(
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
            f"next_action\t{payload['next_action']}",
        ),
    )


__all__ = [
    "profile_record_missing_next_action",
    "profile_record_unreadable_next_action",
    "register_repair_profile_command",
]
