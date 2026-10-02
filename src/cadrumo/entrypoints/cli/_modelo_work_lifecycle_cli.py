"""Behavior for modelo work lifecycle commands."""

from __future__ import annotations

import typer

from ...application.modelo.work_addressing import (
    ModeloWorkRegistryYearMismatchError,
    law_selected_revision_for_work_target,
)
from ...application.modelo.work_create_policy import (
    modelo_work_create_refusal_locale_key,
)
from ...application.modelo.work_lifecycle import (
    lifecycle_continuation_for_work_list,
    lifecycle_continuation_for_work_status,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ...core.i18n.render import tr
from ...core.json_contract import Notice
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.contribuyente.tax_residence import parse_tax_region
from ...domain.modelos.work_unit import WorkUnit
from ._modelo_behavior_support import (
    resolve_year_period,
)
from ._modelo_cli_support import (
    resolve_default_actor,
)
from ._modelo_payloads import WorkCreateResult, WorkDiscardResult, WorkListResult, WorkRenameResult, WorkStatusResult
from ._modelo_rendering import advisory_notice, work_unit_lines, work_unit_list_lines, work_unit_payload
from .common import (
    activate_subcommand_output_language,
    active_profile_label,
    emit_envelope,
    resolve_lifecycle_continuation_notice,
)
from .runtime_modelo_metadata import discard_modelo_work, read_modelo_work_unit, rename_modelo_work
from .runtime_modelo_work_create import create_modelo_work
from .runtime_modelo_work_inventory import read_modelo_work_inventory
from .runtime_registered_operation import submitted_operation_error
from .state_projection_support import authority_operation


def _validate_filing_year(year: int) -> None:
    if not FILING_YEAR_MIN <= year <= FILING_YEAR_MAX:
        raise typer.BadParameter(
            tr("cli.app.modelo.work.year_out_of_range", year=year, minimum=FILING_YEAR_MIN, maximum=FILING_YEAR_MAX)
        )


def guard_unsupported_work_modelo(modelo: str) -> None:
    from .errors import CliRefusedBoundaryError

    modelo_code = modelo.strip()
    locale_key = modelo_work_create_refusal_locale_key(modelo_code)
    if locale_key is None:
        return
    raise CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


def _validate_registry_target_before_profile_if_needed(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
    operation: PinnedAuthorityOperation,
) -> None:
    from ...core.bucket_pointer import resolve_active_bucket_id

    if resolve_active_bucket_id() is not None:
        return
    try:
        law_selected_revision_for_work_target(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            requested_revision_id=registry_revision_id,
            operation=operation,
        )
    except (ModeloWorkRegistryYearMismatchError, RegistrySnapshotError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _emit_work_create_result(
    ctx: typer.Context,
    *,
    unit: WorkUnit,
    reused: bool,
    name: str | None,
    name_applied: str | None,
    allow_not_applicable: bool,
    advisory_keys: tuple[str, ...] = (),
    quiet: bool = False,
) -> None:
    status = "reused" if reused else "created"
    if reused:
        status_message, operation = _reused_work_status_message(name=name, name_applied=name_applied)
    else:
        status_message = tr("cli.app.modelo.work.create_created")
        operation = "modelo.work.create"
    result = WorkCreateResult.model_validate(
        {
            "operation": operation,
            "status": status,
            "status_message": status_message,
            "name_applied": name_applied,
            "applicability_guard_bypassed": allow_not_applicable,
            **work_unit_payload(unit).model_dump(mode="python"),
        }
    )
    obligation_notices, obligation_lines = _work_create_advisory_output(advisory_keys)
    if quiet:
        lines = list(obligation_lines)
    else:
        lines = [
            f"operation\t{operation}",
            f"status\t{status}",
            *work_unit_lines(unit),
            status_message,
            *obligation_lines,
        ]
    emit_envelope(ctx, command="modelo.work.create", result=result, lines=lines, notices=obligation_notices)


def _reused_work_status_message(*, name: str | None, name_applied: str | None) -> tuple[str, str]:
    if name_applied is not None:
        return (tr("cli.app.modelo.work.create_reused_renamed", name=name_applied), "modelo.work.reuse")
    if name is not None and name.strip():
        return (tr("cli.app.modelo.work.create_reused_name_match"), "modelo.work.reuse")
    return (tr("cli.app.modelo.work.create_reused"), "modelo.work.reuse")


def _work_create_advisory_output(advisory_keys: tuple[str, ...]) -> tuple[list[Notice], list[str]]:
    """Localize only the advisory identities released by the profile worker."""
    messages = [tr(key) for key in advisory_keys]
    notices = [advisory_notice("modelo.work.create.filing_obligation", message) for message in messages]
    return notices, messages


__all__ = ["guard_unsupported_work_modelo", "work_create", "work_discard", "work_list", "work_rename", "work_status"]


def work_create(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    revision: str | None = None,
    bucket_id: str | None = None,
    name: str | None = None,
    actor: str | None = None,
    allow_not_applicable: bool = False,
    quiet: bool = False,
    causante_ccaa_raw: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Create or load a modelo work unit. Idempotent on the four-axis key."""
    activate_subcommand_output_language(ctx, output_language)
    _validate_filing_year(year)
    requested_revision = revision.strip() if revision is not None else None
    causante_ccaa = parse_tax_region(causante_ccaa_raw) if causante_ccaa_raw is not None else None
    guard_unsupported_work_modelo(modelo)
    resolved_period = resolve_year_period(year, period, modelo=modelo)
    resolved_year = resolved_period.filing_year
    operation = authority_operation(ctx)
    _validate_registry_target_before_profile_if_needed(
        modelo=modelo,
        filing_year=resolved_year,
        period=resolved_period,
        registry_revision_id=requested_revision,
        operation=operation,
    )
    creation = create_modelo_work(
        ctx,
        modelo=modelo,
        period=resolved_period,
        revision_id=requested_revision,
        bucket_id=bucket_id,
        name=name,
        actor=actor or resolve_default_actor(),
        causante_ccaa=causante_ccaa.value if causante_ccaa is not None else None,
        allow_not_applicable=allow_not_applicable,
    )
    outcome = creation.result
    try:
        _emit_work_create_result(
            ctx,
            unit=outcome.unit.to_work_unit(),
            reused=outcome.reused,
            name=name,
            name_applied=outcome.name_applied,
            allow_not_applicable=outcome.applicability_guard_bypassed,
            advisory_keys=outcome.advisory_keys,
            quiet=quiet,
        )
    except Exception:
        raise submitted_operation_error(
            creation.completion.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=creation.completion.terminal_condition,
            effect=creation.completion.effect,
        ) from None


def work_list(
    ctx: typer.Context,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """List modelo work units. Discarded units are excluded unless asked."""
    activate_subcommand_output_language(ctx, output_language)
    units = read_modelo_work_inventory(
        ctx,
        bucket_id=bucket_id,
        include_discarded=include_discarded,
    )
    result = WorkListResult.model_validate(
        {
            "bucket_id_filter": bucket_id,
            "include_discarded": include_discarded,
            "work_unit_count": len(units),
            "work_units": [work_unit_payload(unit) for unit in units],
        }
    )
    lines = [
        f"active_profile\t{active_profile_label() or ''}",
        *work_unit_list_lines(units, include_discarded=include_discarded),
    ]
    follow_up = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_list(units))
    emit_envelope(ctx, command="modelo.work.list", result=result, lines=lines, notices=[follow_up])


def work_status(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """View one work unit's metadata."""
    activate_subcommand_output_language(ctx, output_language)
    unit = read_modelo_work_unit(
        ctx, work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    result = WorkStatusResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
    lines = [
        f"active_profile\t{active_profile_label() or ''}",
        "operation\tmodelo.work.status",
        *work_unit_lines(unit, include_bucket_id=False),
    ]
    next_step = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_status(unit))
    emit_envelope(ctx, command="modelo.work.status", result=result, lines=lines, notices=[next_step])


def work_rename(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    name: str | None = None,
    actor: str | None = None,
) -> None:
    """Update one work unit's display name."""
    if name is None or not name.strip():
        raise typer.BadParameter(tr("cli.app.modelo.work.name_required"))
    unit = rename_modelo_work(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        name=name,
        actor=actor,
    )
    result = WorkRenameResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.rename", *work_unit_lines(unit)]
    emit_envelope(ctx, command="modelo.work.rename", result=result, lines=lines)


def work_discard(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    confirmed: bool = False,
) -> None:
    """Transition a work unit to discarded state."""
    target_label = work_unit_id or f"{modelo or '?'} {year or '?'} {period or '?'}"
    if not confirmed:
        raise typer.BadParameter(tr("cli.app.modelo.work.discard_requires_yes", work_unit_id=target_label))
    unit = discard_modelo_work(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        actor=actor,
        reason=reason,
    )
    result = WorkDiscardResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.discard", *work_unit_lines(unit)]
    emit_envelope(ctx, command="modelo.work.discard", result=result, lines=lines)
