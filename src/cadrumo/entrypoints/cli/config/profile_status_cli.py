"""The independently loadable ``config profile status`` leaf."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ..common import activate_subcommand_output_language as _activate_output_language
from ..common import emit_envelope, resolve_cli_precondition_action

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.workflow.profile_health import ActiveProfileHealth
    from ....core.json_contract import ResolvedPreconditionAction
    from ....domain.user_profile.values import UserProfileRecord


def _profile_status_inputs() -> tuple[
    ActiveProfileHealth,
    str | None,
    str | None,
    ResolvedPreconditionAction | None,
]:
    """Read the backend health snapshot and its committed display projection."""
    from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from ....application.workflow.profile_health import assess_active_profile_health
    from ....domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        profile_health = assess_active_profile_health(operation=operation)
    active_uuid = profile_health.active_profile
    pointer = read_profile_bucket_by_id(active_uuid) if active_uuid else None
    active_profile = pointer.label if pointer is not None else None
    health_action = (
        resolve_cli_precondition_action(profile_health.precondition_verdict)
        if profile_health.precondition_verdict is not None
        else None
    )
    return profile_health, active_uuid, active_profile, health_action


def _emit_initial_profile_status(
    ctx: typer.Context,
    *,
    profile_health: ActiveProfileHealth,
    active_profile: str | None,
    health_action: ResolvedPreconditionAction | None,
) -> bool:
    """Render health states that do not require loading a profile record.

    ``True`` means the caller may return normally. The two broken pointer/record
    states render their typed envelope before raising the established exit code.
    """
    from ..config_payloads import ConfigStatusResult
    from .status_rendering import precondition_action_lines, unavailable_profile_record_status

    if profile_health.status == "none":
        result = ConfigStatusResult(
            active_profile=None,
            registered_profile=False,
            configured=False,
            precondition_action=health_action,
        )
        emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(tr("cli.config.status.empty_profile"), *precondition_action_lines(health_action)),
        )
        return True
    if profile_health.status == "dangling_pointer":
        result = ConfigStatusResult(
            active_profile=active_profile,
            registered_profile=False,
            configured=False,
            precondition_action=health_action,
        )
        emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(
                # A dangling pointer names a capsule that is gone, so there is no
                # label to read. The sibling emitter below renders an absent label
                # as an empty cell; formatting the Optional directly put a literal
                # Python ``None`` in front of the operator.
                f"profile\t{active_profile or ''}",
                "readiness\tdangling_pointer",
                "registered_profile\tmissing",
                *precondition_action_lines(health_action),
            ),
        )
        raise typer.Exit(code=2)
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        result, lines = unavailable_profile_record_status(
            active_profile=active_profile,
            status=profile_health.status,
            profile_record_error=profile_health.profile_record_error,
            precondition_action=health_action,
        )
        emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    return False


def _load_active_profile_record() -> UserProfileRecord | None:
    """Load the active record through the workflow repository's secure boundary."""
    from ....application.workflow.persistence import workflow_state_repository

    return workflow_state_repository().load().active_profile_record()


def _emit_unavailable_active_profile_record(
    ctx: typer.Context,
    *,
    active_profile: str | None,
    status: str,
    profile_record_error: str | None,
    health_action: ResolvedPreconditionAction | None,
) -> NoReturn:
    """Render and terminate after the active record cannot be read."""
    from .status_rendering import unavailable_profile_record_status

    result, lines = unavailable_profile_record_status(
        active_profile=active_profile,
        status=status,
        profile_record_error=profile_record_error,
        precondition_action=health_action,
    )
    emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
    raise typer.Exit(code=2)


def _emit_incomplete_profile_status(
    ctx: typer.Context,
    *,
    active_profile: str | None,
    active_uuid: str | None,
    values: Mapping[str, str],
    health_action: ResolvedPreconditionAction | None,
    missing_required: tuple[str, ...],
) -> None:
    """Render the backend's incomplete-profile readiness projection."""
    from .status_rendering import blocked_readiness_status

    result, lines = blocked_readiness_status(
        active_profile=active_profile,
        profile_id=active_uuid,
        values=values,
        precondition_action=health_action,
        missing_required=missing_required,
    )
    emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)


def _emit_model_baseline_status(
    ctx: typer.Context,
    *,
    active_profile: str | None,
    record: UserProfileRecord,
    values: Mapping[str, str],
) -> bool:
    """Render the filing-baseline refusal when the health record is otherwise complete."""
    from ....application.modelo.profile_readiness_gate import modelo_work_profile_baseline_missing_paths
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from .status_rendering import blocked_readiness_status

    # The baseline resolves governed vocabularies (the IRPF income categories),
    # which exist only inside a pinned authority operation. Outside one it
    # worked only when an earlier leased call had already cached the answer.
    with bundled_indexed_authority().operation():
        missing = modelo_work_profile_baseline_missing_paths(record)
    if not missing:
        return False
    result, blocked_lines = blocked_readiness_status(
        active_profile=active_profile,
        profile_id=None,
        values=values,
        precondition_action=None,
    )
    lines = (tr("cli.config.status.empty_profile"),) if active_profile is None else blocked_lines
    emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
    return True


def _emit_projected_profile_status(
    ctx: typer.Context,
    *,
    active_profile: str | None,
    active_uuid: str | None,
    values: Mapping[str, str],
) -> None:
    """Validate and render the final configured-profile projection."""
    from pydantic import ValidationError

    from ....application.wizard.catalogue import build_setup_flow
    from ....application.wizard.persistence import project_answers
    from ....core.logging import get_logger
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from ..config_payloads import ConfigStatusResult

    try:
        with bundled_indexed_authority().operation() as operation:
            projection = project_answers(build_setup_flow(operation), values)
    except ValidationError:
        get_logger(__name__).debug("config profile status projection validation failed; reporting profile incomplete")
        result = ConfigStatusResult(
            active_profile=active_profile,
            profile_id=active_uuid,
            tax_id_present=bool(values.get("identity.tax_id")),
            activity_present=bool(values.get("activities.description")),
            configured=False,
        )
        emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(tr("cli.config.status.empty_profile"),),
        )
        return
    result = ConfigStatusResult(
        active_profile=active_profile,
        profile_id=active_uuid,
        tax_id_present=bool(values.get("identity.tax_id")),
        activity_present=bool(values.get("activities.description")),
        configured=True,
        iva_regime=values.get("iva.regime", ""),
        tax_residence_ccaa=values.get("tax_residence.ccaa", ""),
    )
    emit_envelope(
        ctx,
        command="config.profile.status",
        result=result,
        lines=(
            f"profile\t{active_profile or ''}",
            f"profile_id\t{active_uuid or ''}",
            f"identity.tax_id\t{values.get('identity.tax_id', '<unset>')}",
            f"activities.description\t{values.get('activities.description', '<unset>')}",
            f"iva.regime\t{values.get('iva.regime', '<unset>')}",
            f"tax_residence.ccaa\t{values.get('tax_residence.ccaa', '<unset>')}",
            tr("cli.config.status.next_step"),
        ),
    )
    del projection


def config_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show the readiness of the current configuration profile."""
    _activate_output_language(ctx, output_language)

    from ....application.user_profile.projections import record_to_path_values

    profile_health, active_uuid, active_profile, health_action = _profile_status_inputs()
    if _emit_initial_profile_status(
        ctx,
        profile_health=profile_health,
        active_profile=active_profile,
        health_action=health_action,
    ):
        return
    record = _load_active_profile_record()
    if record is None:
        _emit_unavailable_active_profile_record(
            ctx,
            active_profile=active_profile,
            status="missing_profile_record",
            profile_record_error=None,
            health_action=health_action,
        )
    values = record_to_path_values(record)
    if profile_health.status == "incomplete":
        _emit_incomplete_profile_status(
            ctx,
            active_profile=active_profile,
            active_uuid=active_uuid,
            values=values,
            health_action=health_action,
            missing_required=profile_health.missing_required,
        )
        return
    if _emit_model_baseline_status(ctx, active_profile=active_profile, record=record, values=values):
        return
    _emit_projected_profile_status(
        ctx,
        active_profile=active_profile,
        active_uuid=active_uuid,
        values=values,
    )
