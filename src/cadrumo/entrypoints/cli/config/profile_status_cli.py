"""Profile readiness rendered from one runtime-authorized record snapshot."""

from __future__ import annotations

from uuid import UUID

import typer

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.view_operation import ProfileViewPageKind, ProfileViewStatusItem
from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
from ....application.workflow.profile_health import ProfileHealthStatus, assess_active_profile_health
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import ResolvedPreconditionAction
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ..common import activate_subcommand_output_language, emit_envelope, resolve_cli_precondition_action
from ..config_payloads import ConfigStatusResult
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from .runtime_profile_view import resolve_runtime_profile_output_language
from .status_rendering import blocked_readiness_status, precondition_action_lines


def _unregistered_status(ctx: typer.Context) -> None:
    """Retain public empty/dangling diagnostics without opening profile custody."""
    with bundled_indexed_authority().operation() as operation:
        health = assess_active_profile_health(operation=operation, include_private_record=False)
    # Dispatch permits this route only when public discovery found no live
    # capsule. A concurrent registration must not turn it into a private read.
    if health.status not in {ProfileHealthStatus.NONE, ProfileHealthStatus.DANGLING_POINTER}:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    action = (
        resolve_cli_precondition_action(health.precondition_verdict)
        if health.precondition_verdict is not None
        else None
    )
    result = ConfigStatusResult(
        active_profile=None, registered_profile=False, configured=False, precondition_action=action
    )
    lines = (
        (tr("cli.config.status.empty_profile"), *precondition_action_lines(action))
        if health.status is ProfileHealthStatus.NONE
        else (
            "profile\t",
            "readiness\tdangling_pointer",
            "registered_profile\tmissing",
            *precondition_action_lines(action),
        )
    )
    emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
    if health.status is ProfileHealthStatus.DANGLING_POINTER:
        raise typer.Exit(code=2)


def _emit_runtime_status(ctx: typer.Context, status: ProfileViewStatusItem, *, profile_id: UUID) -> None:
    """Render canonical completeness and baseline outcomes without re-evaluating them."""
    health = status.health
    if health.active_profile != str(profile_id) or health.status not in {
        ProfileHealthStatus.INCOMPLETE,
        ProfileHealthStatus.READY,
    }:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    values = {fact.path: fact.value for fact in status.facts}
    if len(values) != len(status.facts) or set(values) - {
        "identity.tax_id",
        "activities.description",
        "iva.regime",
        "tax_residence.ccaa",
    }:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    action = (
        resolve_cli_precondition_action(health.precondition_verdict.to_verdict())
        if health.precondition_verdict is not None
        else None
    )
    if health.status is ProfileHealthStatus.INCOMPLETE or not status.baseline_ready:
        result, lines = _blocked_runtime_status(status, profile_id, values, action)
    elif not status.projection_valid:
        result = ConfigStatusResult(
            active_profile=status.display_name,
            profile_id=str(profile_id),
            tax_id_present=bool(values.get("identity.tax_id")),
            activity_present=bool(values.get("activities.description")),
            configured=False,
        )
        lines = (tr("cli.config.status.empty_profile"),)
    else:
        result = ConfigStatusResult(
            active_profile=status.display_name,
            profile_id=str(profile_id),
            tax_id_present=bool(values.get("identity.tax_id")),
            activity_present=bool(values.get("activities.description")),
            configured=True,
            iva_regime=values.get("iva.regime", ""),
            tax_residence_ccaa=values.get("tax_residence.ccaa", ""),
        )
        lines = (
            f"profile\t{status.display_name}",
            f"profile_id\t{profile_id}",
            f"identity.tax_id\t{values.get('identity.tax_id', '<unset>')}",
            f"activities.description\t{values.get('activities.description', '<unset>')}",
            f"iva.regime\t{values.get('iva.regime', '<unset>')}",
            f"tax_residence.ccaa\t{values.get('tax_residence.ccaa', '<unset>')}",
            tr("cli.config.status.next_step"),
        )
    emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)


def config_status(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """Show readiness through exact profile authority; keep unregistered diagnostics public."""
    activate_subcommand_output_language(ctx, output_language)
    active = resolve_active_bucket_id()
    if active is None or read_profile_bucket_by_id(active) is None:
        _unregistered_status(ctx)
        return
    profile_id = UUID(active)
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    language = resolve_runtime_profile_output_language(client, requested=output_language)
    activate_subcommand_output_language(ctx, language)
    try:
        collection = client.read_profile_view((ProfileViewPageKind.STATUS,), output_language=language)
    except RuntimeFrontendRefusedError as error:
        raise CliRefusedBoundaryError(error.reason, context={"reason": error.reason}) from error
    items = collection.items(ProfileViewPageKind.STATUS)
    if len(items) != 1 or not isinstance(items[0], ProfileViewStatusItem):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    _emit_runtime_status(ctx, items[0], profile_id=profile_id)


def _blocked_runtime_status(
    status: ProfileViewStatusItem, profile_id: UUID, values: dict[str, str], action: ResolvedPreconditionAction | None
) -> tuple[ConfigStatusResult, tuple[str, ...]]:
    """Render incomplete and baseline-blocked status without re-evaluating profile facts."""
    health = status.health
    incomplete = health.status is ProfileHealthStatus.INCOMPLETE
    result, lines = blocked_readiness_status(
        active_profile=status.display_name,
        profile_id=str(profile_id) if incomplete else None,
        values=values,
        precondition_action=action if incomplete else None,
        missing_required=health.missing_required if incomplete else (),
    )
    return result, lines
