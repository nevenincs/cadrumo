"""The independently loadable ``config profile status`` leaf."""

from __future__ import annotations

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import activate_subcommand_output_language as _activate_output_language


def config_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show the readiness of the current configuration profile."""
    _activate_output_language(ctx, output_language)
    from pydantic import ValidationError

    from ....application.user_profile import record_to_path_values
    from ....application.wizard import project_answers
    from ....application.workflow import (
        assess_active_profile_health,
        read_profile_bucket_by_id,
        workflow_state_repository,
    )
    from ....core.logging import get_logger
    from ....core.wizard_catalogue import get_setup_flow
    from .._config_payloads import ConfigStatusResult
    from ._status_rendering import (
        blocked_readiness_status,
        precondition_action_lines,
        unavailable_profile_record_status,
    )

    profile_health = assess_active_profile_health()
    active_uuid = profile_health.active_profile
    pointer = read_profile_bucket_by_id(active_uuid) if active_uuid else None
    active_profile = pointer.label if pointer is not None else None
    health_action = (
        resolve_cli_precondition_action(profile_health.precondition_verdict)
        if profile_health.precondition_verdict is not None
        else None
    )
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
        return
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
                f"profile\t{active_profile}",
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
    record = workflow_state_repository().load().active_profile_record()
    if record is None:
        result, lines = unavailable_profile_record_status(
            active_profile=active_profile,
            status="missing_profile_record",
            profile_record_error=None,
            precondition_action=health_action,
        )
        emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    values = record_to_path_values(record)
    if profile_health.status == "incomplete":
        result, lines = blocked_readiness_status(
            active_profile=active_profile,
            profile_id=active_uuid,
            values=values,
            precondition_action=health_action,
            missing_required=profile_health.missing_required,
        )
        emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        return
    from ....application.modelo import modelo_work_profile_baseline_missing_paths

    if modelo_work_profile_baseline_missing_paths(record):
        result, blocked_lines = blocked_readiness_status(
            active_profile=active_profile,
            profile_id=None,
            values=values,
            precondition_action=None,
        )
        lines = (tr("cli.config.status.empty_profile"),) if active_profile is None else blocked_lines
        emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        return
    try:
        projection = project_answers(get_setup_flow(), values)
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
