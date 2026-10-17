"""Profile repair behavior handlers for ``aeat config repair``.

Renders the application's profile-record inspection and pointer repair; the
work itself is the application's, shared with the runtime's repair act.
"""

from __future__ import annotations

import typing

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

from ....core.json_contract import strict_round_trip
from ....core.redaction.rules import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ..common import emit_envelope, resolve_cli_precondition_action
from .status_rendering import precondition_action_lines

if typing.TYPE_CHECKING:
    from ....application.workflow.profile_bucket_models import ProfileBucketPointer


def repair_profile(
    ctx: typer.Context,
    profile: str | None = None,
    clear_active: bool = False,
    yes: bool = False,
) -> None:
    """Inspect profile health or safely repair a degraded active-profile pointer."""
    from ....application.workflow.profile_repair import pointer_repair_refusal
    from ._profile_support import resolve_profile_by_label

    pointer = resolve_profile_by_label(profile) if profile is not None else None
    if pointer is not None and not clear_active:
        _emit_profile_record_status(ctx, pointer)
        return
    named = None if profile is None or pointer is None else (profile, pointer)
    refusal = pointer_repair_refusal(named, clear_active=clear_active, confirmed=yes)
    if refusal is not None:
        raise _CliRefusedBoundaryError(translated_message=refusal.message_key, context=refusal.context)
    _emit_pointer_repair(ctx, clear_active=clear_active, confirmed=yes)


def _emit_pointer_repair(ctx: typer.Context, *, clear_active: bool, confirmed: bool) -> None:
    """Repair a degraded active-profile pointer and emit the health result."""
    from cadrumo_client.commands.payloads import RepairProfileResult

    from ....application.diagnostics_repair_documents import (
        profile_health_reference,
        profile_pointer_repair_document,
    )
    from ....application.workflow.profile_health import repair_active_profile_pointer
    from ..state_projection_support import authority_operation

    result = repair_active_profile_pointer(
        clear_active=clear_active,
        confirmed=confirmed,
        operation=authority_operation(ctx),
    )
    health = result.after or result.before
    active_profile = profile_health_reference(health)
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
    repair_payload = strict_round_trip(
        RepairProfileResult,
        profile_pointer_repair_document(result, resolve_action=resolve_cli_precondition_action),
    )
    health_payload = repair_payload.after or repair_payload.before
    if health_payload is not None:
        lines.extend(precondition_action_lines(health_payload.precondition_action))
    emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)


def _emit_profile_record_status(ctx: typer.Context, pointer: ProfileBucketPointer) -> None:
    """Emit a non-secret status report for one registered profile bucket.

    A record that could not be read is reported and then exits with status 2.
    """
    from cadrumo_client.commands.payloads import RepairProfileResult

    from ....application.diagnostics_repair_documents import profile_record_document
    from ....application.workflow.profile_health import ProfileHealthStatus
    from ....application.workflow.profile_repair import inspect_profile_record
    from ...diagnostics_repair_composition import read_session_profile_record

    inspection = inspect_profile_record(pointer, read_profile_record=read_session_profile_record)
    repair_payload = strict_round_trip(
        RepairProfileResult,
        profile_record_document(inspection, resolve_action=resolve_cli_precondition_action),
    )
    identity_lines = (
        f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
        f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
    )
    display_line = f"display_name\t{inspection.display_name}"
    if inspection.setup_state is not None:
        emit_envelope(
            ctx,
            command="config.repair.profile",
            result=repair_payload,
            lines=(
                "readiness\tready",
                display_line,
                *identity_lines,
                "registered_bucket\tpresent",
                "profile_record\tpresent",
                f"setup_state\t{inspection.setup_state.value}",
            ),
        )
        return
    unreadable = inspection.status == ProfileHealthStatus.PROFILE_RECORD_UNREADABLE
    emit_envelope(
        ctx,
        command="config.repair.profile",
        result=repair_payload,
        lines=(
            f"readiness\t{'profile_record_unreadable' if unreadable else 'missing_profile_record'}",
            *identity_lines,
            display_line,
            "registered_bucket\tpresent",
            f"profile_record\t{'unreadable' if unreadable else 'missing'}",
            *precondition_action_lines(repair_payload.precondition_action),
        ),
    )
    raise typer.Exit(code=2)


__all__ = ["repair_profile"]
