"""Behavior for modelo work lifecycle commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import typer

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo._action_errors import (
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ...application.modelo._profile_readiness_gate import (
    require_existing_profile_baseline_ready_for_modelo_work,
    require_profile_ready_for_modelo_work,
)
from ...application.modelo._work_create_policy import (
    guard_active_profile_foral_ccaa,
    modelo_work_create_applicability_refusal,
    modelo_work_create_refusal_locale_key,
)
from ...application.modelo.work_addressing import (
    ModeloWorkRegistryYearMismatchError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    ensure_modelo_work_unit_for_active_target,
    law_selected_revision_for_work_target,
)
from ...application.modelo.work_lifecycle import (
    discard_work_unit,
    lifecycle_continuation_for_work_list,
    lifecycle_continuation_for_work_status,
    list_work_units,
    rename_work_unit,
)
from ...core import Modelo
from ...core.period import Period
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ...core.i18n import tr
from ...core.json_contract import Notice
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.contribuyente.tax_residence import parse_tax_region
from ...domain.modelos.work_unit import WorkUnit
from ._common import (
    activate_subcommand_output_language,
    active_profile_label,
    emit_envelope,
    resolve_lifecycle_continuation_notice,
)
from ._modelo_behavior_support import (
    require_active_profile,
    resolve_work_unit_for_cli,
    resolve_year_period,
)
from ._modelo_cli_support import (
    bad_parameter_from_error,
    resolve_default_actor,
    resolve_explicit_or_active_bucket_id,
    selector_bad_parameter,
)
from ._modelo_payloads import WorkCreateResult, WorkDiscardResult, WorkListResult, WorkRenameResult, WorkStatusResult
from ._modelo_rendering import advisory_notice, work_unit_lines, work_unit_list_lines, work_unit_payload


@dataclass(frozen=True, slots=True)
class _LifecycleDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    guard_foral_profile_ccaa: Callable[[], None]
    resolve_year_period: Callable[..., Period]
    resolve_work_unit_for_cli: Callable[..., WorkUnit]
    resolve_default_actor: Callable[[], str]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]
    selector_bad_parameter: Callable[[BaseException], typer.BadParameter]


def _validate_filing_year(year: int) -> None:
    if not FILING_YEAR_MIN <= year <= FILING_YEAR_MAX:
        raise typer.BadParameter(
            tr("cli.app.modelo.work.year_out_of_range", year=year, minimum=FILING_YEAR_MIN, maximum=FILING_YEAR_MAX)
        )


def _guard_modelo_applicability(modelo: str, *, allow_not_applicable: bool) -> None:
    from .errors import CliRefusedBoundaryError

    refusal = modelo_work_create_applicability_refusal(modelo, allow_not_applicable=allow_not_applicable)
    if refusal is None:
        return
    raise CliRefusedBoundaryError(
        translated_message="cli.app.modelo.work.create_not_applicable_refused",
        context={"modelo": refusal.modelo, "reason": refusal.reason},
    )


def guard_unsupported_work_modelo(modelo: str) -> None:
    from .errors import CliRefusedBoundaryError

    modelo_code = modelo.strip()
    locale_key = modelo_work_create_refusal_locale_key(modelo_code)
    if locale_key is None:
        return
    raise CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


def _validate_registry_target_before_profile_if_needed(
    *, modelo: str, filing_year: int, period: Period, registry_revision_id: RevisionId | None
) -> None:
    from ...core.bucket_pointer import resolve_active_bucket_id

    if resolve_active_bucket_id() is not None:
        return
    try:
        law_selected_revision_for_work_target(
            modelo=modelo, filing_year=filing_year, period=period, requested_revision_id=registry_revision_id
        )
    except (ModeloWorkRegistryYearMismatchError, RegistrySnapshotError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _emit_work_create_result(
    ctx: typer.Context,
    *,
    unit,
    reused: bool,
    name: str | None,
    name_applied: str | None,
    allow_not_applicable: bool,
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
    obligation_notices, obligation_lines = _modelo_100_obligation_advisory_output(unit)
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


def _modelo_100_obligation_advisory_output(unit) -> tuple[list[Notice], list[str]]:
    """Project M100 filing-obligation advisories onto notices and text lines.

    The advisory rides on the envelope ``notices`` channel (warning
    severity) so JSON consumers receive the same filing-obligation
    guidance the text surface already showed; the text lines are
    rebuilt from the same advisory messages so the two cannot drift.
    """
    if unit.modelo != Modelo.M100:
        return ([], [])
    from ...application.overview.status_report import build_filing_obligation_advisories
    from ...application.user_profile.profile_record_repository import ProfileRecordRepository
    from ...application.user_profile.projections import record_to_values
    from ...core.bucket_pointer import resolve_active_bucket_id

    bucket = resolve_active_bucket_id()
    if bucket is None:
        return ([], [])
    record = ProfileRecordRepository.for_current_session(bucket).load(bucket)
    raw = record_to_values(record) if record is not None else None
    messages = [tr(advisory_key) for advisory_key in build_filing_obligation_advisories(raw)]
    notices = [advisory_notice("modelo.work.create.filing_obligation", message) for message in messages]
    return (notices, messages)


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
    _validate_registry_target_before_profile_if_needed(
        modelo=modelo, filing_year=resolved_year, period=resolved_period, registry_revision_id=requested_revision
    )
    require_active_profile()
    guard_active_profile_foral_ccaa()
    _guard_modelo_applicability(modelo, allow_not_applicable=allow_not_applicable)
    resolved_bucket = resolve_explicit_or_active_bucket_id(bucket_id)
    resolved_actor = actor or resolve_default_actor()
    require_existing_profile_baseline_ready_for_modelo_work(
        bucket_id=resolved_bucket,
        modelo=modelo,
        filing_year=resolved_year,
        period=resolved_period,
        enforce_applicability=not allow_not_applicable,
    )
    resolved_revision_id = law_selected_revision_for_work_target(
        modelo=modelo, filing_year=resolved_year, period=resolved_period, requested_revision_id=requested_revision
    )
    require_profile_ready_for_modelo_work(
        bucket_id=resolved_bucket,
        modelo=modelo,
        revision_id=resolved_revision_id,
        filing_year=resolved_year,
        period=resolved_period,
        enforce_applicability=not allow_not_applicable,
    )
    try:
        ensure_result = ensure_modelo_work_unit_for_active_target(
            bucket_id=resolved_bucket,
            modelo=modelo,
            filing_year=resolved_year,
            period=resolved_period,
            registry_revision_id=requested_revision,
            name=name,
            actor=resolved_actor,
            causante_ccaa=causante_ccaa,
            enforce_applicability=not allow_not_applicable,
            catalogue=WorkUnitCatalogueRepository(bucket_id=resolved_bucket).load(),
        )
    except (ModeloWorkRegistryYearMismatchError, RegistrySnapshotError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except (
        ModeloWorkSelectorContradictionError,
        ModeloWorkUnitNotFoundError,
        ModeloWorkVisibleTargetAmbiguousError,
        ModeloWorkRevisionConflictError,
    ) as exc:
        raise selector_bad_parameter(exc) from exc
    _emit_work_create_result(
        ctx,
        unit=ensure_result.work_unit,
        reused=ensure_result.reused,
        name=name,
        name_applied=ensure_result.name_applied,
        allow_not_applicable=allow_not_applicable,
        quiet=quiet,
    )


def work_list(
    ctx: typer.Context,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """List modelo work units. Discarded units are excluded unless asked."""
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    units = list_work_units(bucket_id=bucket_id, include_discarded=include_discarded)
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
    require_active_profile()
    unit = resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
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
    require_active_profile()
    if name is None or not name.strip():
        raise typer.BadParameter(tr("cli.app.modelo.work.name_required"))
    unit = resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    try:
        unit = rename_work_unit(unit.work_unit_id, name, actor=actor or resolve_default_actor())
    except WorkUnitMutationRefusedError:
        raise
    except WorkUnitNotFoundError as exc:
        raise bad_parameter_from_error(exc) from exc
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
    require_active_profile()
    unit = resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    try:
        unit = discard_work_unit(unit.work_unit_id, actor=actor or resolve_default_actor(), reason=reason)
    except WorkUnitAlreadyDiscardedError:
        raise
    except WorkUnitNotFoundError as exc:
        raise bad_parameter_from_error(exc) from exc
    result = WorkDiscardResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.discard", *work_unit_lines(unit)]
    emit_envelope(ctx, command="modelo.work.discard", result=result, lines=lines)
