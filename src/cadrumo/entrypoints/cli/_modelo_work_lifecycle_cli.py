"""Typer registration for modelo work lifecycle commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import typer

from ...application.modelo import (
    ModeloWorkRegistryYearMismatchError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    discard_work_unit,
    ensure_modelo_work_unit_for_active_target,
    lifecycle_continuation_for_work_list,
    lifecycle_continuation_for_work_status,
    list_work_units,
    modelo_work_create_applicability_refusal,
    modelo_work_create_refusal_locale_key,
    rename_work_unit,
    require_existing_profile_baseline_ready_for_modelo_work,
    require_profile_ready_for_modelo_work,
    resolve_registry_revision_for_work_target,
)
from ...core import Modelo, Period
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import (
    Notice,
)
from ...domain.calculations.registry import RegistrySnapshotError, RevisionId
from ...domain.contribuyente import parse_tax_region
from ...domain.modelos import WorkUnit
from ._command_policy import command_execution_policy
from ._common import _emit_envelope, active_profile_label, resolve_lifecycle_continuation_notice
from ._modelo_cli_support import resolve_explicit_or_active_bucket_id
from ._modelo_execution_policies import MODEL_DESTRUCTIVE, MODEL_READ, MODEL_WRITE
from ._modelo_payloads import (
    WorkCreateResult,
    WorkDiscardResult,
    WorkListResult,
    WorkRenameResult,
    WorkStatusResult,
)
from ._modelo_rendering import (
    advisory_notice,
    work_unit_lines,
    work_unit_list_lines,
    work_unit_payload,
)
from ._modelo_work_options import (
    _ActorOpt,
    _BucketIdOpt,
    _ModeloOpt,
    _NameOpt,
    _PeriodOpt,
    _RevisionOpt,
    _WorkUnitIdArg,
    _YearOpt,
)

_FILING_YEAR_MIN = 2000
_FILING_YEAR_MAX = 2099


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


def register_work_lifecycle_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    guard_foral_profile_ccaa: Callable[[], None],
    resolve_year_period: Callable[..., Period],
    resolve_work_unit_for_cli: Callable[..., WorkUnit],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    selector_bad_parameter: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register work lifecycle commands on the modelo work app."""
    deps = _LifecycleDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        guard_foral_profile_ccaa=guard_foral_profile_ccaa,
        resolve_year_period=resolve_year_period,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
        selector_bad_parameter=selector_bad_parameter,
    )
    _register_work_create_command(work_app, deps)
    _register_work_list_command(work_app, deps)
    _register_work_status_command(work_app, deps)
    _register_work_rename_command(work_app, deps)
    _register_work_discard_command(work_app, deps)


def _validate_filing_year(year: int) -> None:
    if not _FILING_YEAR_MIN <= year <= _FILING_YEAR_MAX:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.year_out_of_range",
                year=year,
                minimum=_FILING_YEAR_MIN,
                maximum=_FILING_YEAR_MAX,
            ),
        )


def _guard_modelo_applicability(modelo: str, *, allow_not_applicable: bool) -> None:
    from ._errors import CliRefusedBoundaryError

    refusal = modelo_work_create_applicability_refusal(
        modelo,
        allow_not_applicable=allow_not_applicable,
    )
    if refusal is None:
        return
    raise CliRefusedBoundaryError(
        translated_message="cli.app.modelo.work.create_not_applicable_refused",
        context={
            "modelo": refusal.modelo,
            "reason": refusal.reason,
        },
    )


def guard_unsupported_work_modelo(modelo: str) -> None:
    from ._errors import CliRefusedBoundaryError

    modelo_code = modelo.strip()
    locale_key = modelo_work_create_refusal_locale_key(modelo_code)
    if locale_key is None:
        return

    raise CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


def _register_work_create_command(work_app: typer.Typer, deps: _LifecycleDeps) -> None:
    @work_app.command("create", help=tr("cli.app.modelo.work.create_help"))
    @command_execution_policy(MODEL_WRITE)
    def work_create(
        ctx: typer.Context,
        modelo: Annotated[
            str,
            typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
        ],
        year: Annotated[
            int,
            typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
        ],
        period: Annotated[
            str,
            typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
        ],
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        name: _NameOpt = None,
        actor: _ActorOpt = None,
        allow_not_applicable: Annotated[
            bool,
            typer.Option(
                "--allow-not-applicable",
                help=tr("cli.app.modelo.work.allow_not_applicable_help"),
            ),
        ] = False,
        quiet: Annotated[
            bool,
            typer.Option(
                "--quiet",
                help=tr("cli.app.modelo.work.create_quiet_help"),
            ),
        ] = False,
        causante_ccaa_raw: Annotated[
            str | None,
            typer.Option(
                "--causante-ccaa",
                help=tr("cli.app.modelo.work.causante_ccaa_help"),
            ),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Create or load a modelo work unit. Idempotent on the four-axis key."""
        deps.activate_output_language(ctx, output_language)
        _validate_filing_year(year)
        requested_revision = revision.strip() if revision is not None else None
        causante_ccaa = parse_tax_region(causante_ccaa_raw) if causante_ccaa_raw is not None else None
        guard_unsupported_work_modelo(modelo)
        resolved_period = deps.resolve_year_period(year, period, modelo=modelo)
        resolved_year = resolved_period.filing_year
        _validate_registry_target_before_profile_if_needed(
            modelo=modelo,
            filing_year=resolved_year,
            period=resolved_period,
            registry_revision_id=requested_revision,
        )
        deps.require_active_profile()
        deps.guard_foral_profile_ccaa()
        _guard_modelo_applicability(modelo, allow_not_applicable=allow_not_applicable)
        resolved_bucket = resolve_explicit_or_active_bucket_id(bucket_id)
        resolved_actor = actor or deps.resolve_default_actor()
        require_existing_profile_baseline_ready_for_modelo_work(
            bucket_id=resolved_bucket,
            modelo=modelo,
            filing_year=resolved_year,
            period=resolved_period,
            enforce_applicability=not allow_not_applicable,
        )
        resolved_revision_id = resolve_registry_revision_for_work_target(
            modelo=modelo,
            filing_year=resolved_year,
            period=resolved_period,
            registry_revision_id=requested_revision,
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
            )
        except (ModeloWorkRegistryYearMismatchError, RegistrySnapshotError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        except (
            ModeloWorkSelectorContradictionError,
            ModeloWorkUnitNotFoundError,
            ModeloWorkVisibleTargetAmbiguousError,
            ModeloWorkRevisionConflictError,
        ) as exc:
            raise deps.selector_bad_parameter(exc) from exc

        _emit_work_create_result(
            ctx,
            unit=ensure_result.work_unit,
            reused=ensure_result.reused,
            name=name,
            name_applied=ensure_result.name_applied,
            allow_not_applicable=allow_not_applicable,
            quiet=quiet,
        )


def _validate_registry_target_before_profile_if_needed(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
) -> None:
    from ...core import resolve_active_bucket_id

    if resolve_active_bucket_id() is not None:
        return
    try:
        resolve_registry_revision_for_work_target(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            registry_revision_id=registry_revision_id,
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
        },
    )
    obligation_notices, obligation_lines = _modelo_100_obligation_advisory_output(unit)
    # ``--quiet`` trims the human success prose (operation/status header,
    # work-unit summary, confirmation message) for text mode only. The
    # notice channel is preserved verbatim — obligation advisories still
    # print — and the JSON envelope (``result`` + ``notices``) is emitted
    # unchanged regardless, since ``_emit_envelope`` ignores ``lines`` in
    # JSON mode. Errors raise before reaching this emit path.
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
    _emit_envelope(ctx, command="modelo.work.create", result=result, lines=lines, notices=obligation_notices)


def _reused_work_status_message(*, name: str | None, name_applied: str | None) -> tuple[str, str]:
    if name_applied is not None:
        return (
            tr(
                "cli.app.modelo.work.create_reused_renamed",
                name=name_applied,
            ),
            "modelo.work.reuse",
        )
    if name is not None and name.strip():
        return (
            tr(
                "cli.app.modelo.work.create_reused_name_match",
            ),
            "modelo.work.reuse",
        )
    return (
        tr(
            "cli.app.modelo.work.create_reused",
        ),
        "modelo.work.reuse",
    )


def _modelo_100_obligation_advisory_output(unit) -> tuple[list[Notice], list[str]]:
    """Project M100 filing-obligation advisories onto notices and text lines.

    The advisory rides on the envelope ``notices`` channel (warning
    severity) so JSON consumers receive the same filing-obligation
    guidance the text surface already showed; the text lines are
    rebuilt from the same advisory messages so the two cannot drift.
    """
    if unit.modelo != Modelo.M100:
        return [], []
    from ...application.overview import build_filing_obligation_advisories
    from ...application.user_profile import ProfileRecordRepository, record_to_values
    from ...core import resolve_active_bucket_id

    bucket = resolve_active_bucket_id()
    if bucket is None:
        return [], []
    record = ProfileRecordRepository.for_current_session(bucket).load(bucket)
    raw = record_to_values(record) if record is not None else None
    messages = [tr(advisory_key) for advisory_key in build_filing_obligation_advisories(raw)]
    notices = [advisory_notice("modelo.work.create.filing_obligation", message) for message in messages]
    return notices, messages


def _register_work_list_command(work_app: typer.Typer, deps: _LifecycleDeps) -> None:
    @work_app.command("list", help=tr("cli.app.modelo.work.list_help"))
    @command_execution_policy(MODEL_READ)
    def work_list(
        ctx: typer.Context,
        bucket_id: _BucketIdOpt = None,
        include_discarded: Annotated[
            bool,
            typer.Option(
                "--include-discarded",
                help=tr("cli.app.modelo.work.include_discarded_help"),
            ),
        ] = False,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """List modelo work units. Discarded units are excluded unless asked."""
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        units = list_work_units(bucket_id=bucket_id, include_discarded=include_discarded)
        result = WorkListResult.model_validate(
            {
                "bucket_id_filter": bucket_id,
                "include_discarded": include_discarded,
                "work_unit_count": len(units),
                "work_units": [work_unit_payload(unit) for unit in units],
            },
        )
        lines = [
            f"active_profile\t{active_profile_label() or ''}",
            *work_unit_list_lines(units, include_discarded=include_discarded),
        ]
        follow_up = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_list(units))
        _emit_envelope(ctx, command="modelo.work.list", result=result, lines=lines, notices=[follow_up])


def _register_work_status_command(work_app: typer.Typer, deps: _LifecycleDeps) -> None:
    @work_app.command("status", help=tr("cli.app.modelo.work.status_help"))
    @command_execution_policy(MODEL_READ)
    def work_status(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """View one work unit's metadata."""
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        unit = deps.resolve_work_unit_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        result = WorkStatusResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
        lines = [
            f"active_profile\t{active_profile_label() or ''}",
            "operation\tmodelo.work.status",
            *work_unit_lines(unit, include_bucket_id=False),
        ]
        next_step = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_status(unit))
        _emit_envelope(ctx, command="modelo.work.status", result=result, lines=lines, notices=[next_step])


def _register_work_rename_command(work_app: typer.Typer, deps: _LifecycleDeps) -> None:
    @work_app.command("rename", help=tr("cli.app.modelo.work.rename_help"))
    @command_execution_policy(MODEL_WRITE)
    def work_rename(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        name: _NameOpt = None,
        actor: _ActorOpt = None,
    ) -> None:
        """Update one work unit's display name."""
        deps.require_active_profile()
        if name is None or not name.strip():
            raise typer.BadParameter(tr("cli.app.modelo.work.name_required"))
        unit = deps.resolve_work_unit_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        try:
            unit = rename_work_unit(unit.work_unit_id, name, actor=actor or deps.resolve_default_actor())
        except WorkUnitMutationRefusedError:
            raise
        except WorkUnitNotFoundError as exc:
            raise deps.bad_parameter_from_error(exc) from exc
        result = WorkRenameResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
        lines = ["operation\tmodelo.work.rename", *work_unit_lines(unit)]
        _emit_envelope(ctx, command="modelo.work.rename", result=result, lines=lines)


def _register_work_discard_command(work_app: typer.Typer, deps: _LifecycleDeps) -> None:
    @work_app.command("discard", help=tr("cli.app.modelo.work.discard_help"))
    @command_execution_policy(MODEL_DESTRUCTIVE)
    def work_discard(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        actor: _ActorOpt = None,
        reason: Annotated[
            str | None,
            typer.Option("--reason", help=tr("cli.app.modelo.work.reason_help")),
        ] = None,
        confirmed: Annotated[
            bool,
            typer.Option("--yes", help=tr("cli.app.modelo.work.discard_yes_help")),
        ] = False,
    ) -> None:
        """Transition a work unit to discarded state."""
        target_label = work_unit_id or f"{modelo or '?'} {year or '?'} {period or '?'}"
        if not confirmed:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.discard_requires_yes",
                    work_unit_id=target_label,
                ),
            )
        deps.require_active_profile()
        unit = deps.resolve_work_unit_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        try:
            unit = discard_work_unit(unit.work_unit_id, actor=actor or deps.resolve_default_actor(), reason=reason)
        except WorkUnitAlreadyDiscardedError:
            raise
        except WorkUnitNotFoundError as exc:
            raise deps.bad_parameter_from_error(exc) from exc
        result = WorkDiscardResult.model_validate(work_unit_payload(unit).model_dump(mode="python"))
        lines = ["operation\tmodelo.work.discard", *work_unit_lines(unit)]
        _emit_envelope(ctx, command="modelo.work.discard", result=result, lines=lines)


__all__ = ["guard_unsupported_work_modelo", "register_work_lifecycle_commands"]
