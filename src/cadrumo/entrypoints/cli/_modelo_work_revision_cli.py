"""Typer registration for modelo work :class:`CalculationRevision` read commands.

The registered commands list stored calculation revisions, show one persisted
revision, and render its typed casilla observations without mutating modelo
state. Selection stays in the injected application-facing resolvers; this
transport module serializes results into
:class:`WorkRevisionsResult`,
:class:`WorkRevisionResult`,
and
:class:`WorkObservationsResult`
schemas before handing them to
:func:`_emit_envelope`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    ModeloCalculationRevisionSelector,
    list_calculation_revisions,
    modelo_202_modality_for_work_unit,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...domain.modelos import CalculationRevision, WorkUnit
from ._command_policy import command_execution_policy
from ._common import _emit_envelope
from ._modelo_cli_support import OutputLanguageOpt
from ._modelo_execution_policies import MODEL_READ
from ._modelo_payloads import WorkObservationsResult, WorkRevisionResult, WorkRevisionsResult
from ._modelo_rendering import (
    calculation_observation_lines,
    calculation_revision_lines,
    calculation_revision_payload,
    short_id,
)
from ._modelo_work_options import (
    _BucketIdOpt,
    _CalculationRevisionIdArg,
    _ModeloOpt,
    _PeriodOpt,
    _RegistryRevisionOpt,
    _RevisionOpt,
    _RevisionSelectorOpt,
    _WorkUnitIdArg,
    _WorkUnitIdOpt,
    _YearOpt,
)


@dataclass(frozen=True)
class _WorkRevisionCommandDeps:
    """Injected application and rendering dependencies for revision read handlers."""

    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., WorkUnit]
    resolve_revision_for_cli: Callable[..., CalculationRevision]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]
    selector_bad_parameter: Callable[[BaseException], typer.BadParameter]


def _resolve_selected_revision(
    deps: _WorkRevisionCommandDeps,
    *,
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    registry_revision: str | None,
    bucket_id: str | None,
    selector: str,
) -> CalculationRevision:
    """Resolve the selected :class:`CalculationRevision` for read-only commands."""
    try:
        return deps.resolve_revision_for_cli(
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=registry_revision,
            bucket_id=bucket_id,
            selector=selector,
        )
    except CalculationRevisionNotFoundError as exc:
        if calculation_revision_id is not None:
            raise deps.bad_parameter_from_error(exc) from exc
        raise deps.selector_bad_parameter(exc) from exc


def _register_work_revisions_command(work_app: typer.Typer, deps: _WorkRevisionCommandDeps) -> None:
    @work_app.command("revisions", help=tr("cli.app.modelo.work.revisions_help"))
    @command_execution_policy(MODEL_READ)
    def work_revisions(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """List persisted :class:`CalculationRevision` rows for an optional :class:`WorkUnit`."""
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        resolved_work_unit_id = work_unit_id
        if work_unit_id is not None or modelo is not None or year is not None or period is not None:
            unit = deps.resolve_work_unit_for_cli(
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                revision=revision,
                bucket_id=bucket_id,
            )
            resolved_work_unit_id = unit.work_unit_id
        revisions = list_calculation_revisions(work_unit_id=resolved_work_unit_id)

        result = WorkRevisionsResult.model_validate(
            {
                "work_unit_id_filter": resolved_work_unit_id,
                "revision_count": len(revisions),
                "revisions": [calculation_revision_payload(rev) for rev in revisions],
            },
        )
        lines = [
            "operation\tmodelo.work.revisions",
            f"work_unit_id_filter\t{resolved_work_unit_id or ''}",
            f"revision_count\t{len(revisions)}",
            "short_calculation_revision_id\tcalculation_revision_id\tshort_work_unit_id\twork_unit_id\tstate\tcreated_at",
        ]
        lines.extend(
            "\t".join(
                (
                    short_id(rev.calculation_revision_id) or "",
                    rev.calculation_revision_id,
                    short_id(rev.work_unit_id) or "",
                    rev.work_unit_id,
                    rev.state.value,
                    rev.created_at.isoformat(),
                ),
            )
            for rev in revisions
        )
        _emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)


def _register_work_revision_command(work_app: typer.Typer, deps: _WorkRevisionCommandDeps) -> None:
    @work_app.command("revision", help=tr("cli.app.modelo.work.revision_show_help"))
    @command_execution_policy(MODEL_READ)
    def work_revision(
        ctx: typer.Context,
        calculation_revision_id: _CalculationRevisionIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        registry_revision: _RegistryRevisionOpt = None,
        work_unit_id: _WorkUnitIdOpt = None,
        select: _RevisionSelectorOpt = ModeloCalculationRevisionSelector.CURRENT.value,
        bucket_id: _BucketIdOpt = None,
        verbose: Annotated[
            bool,
            typer.Option(
                "--verbose",
                help=tr(
                    "cli.app.modelo.work.revision_verbose_help",
                    default="Expose the full per-casilla formula trace (op, formula_id, operand refs and values).",
                ),
            ),
        ] = False,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Show one selected :class:`CalculationRevision` as a work-revision result.

        The JSON branch emits
        :class:`WorkRevisionResult`.
        Each computed casilla renders its formula trace inline as
        ``op(refs) = op(values) = value``; ``--verbose`` additionally surfaces
        the full operand lineage line beneath each computed row.
        """
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        selected_revision = _resolve_selected_revision(
            deps,
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=registry_revision,
            bucket_id=bucket_id,
            selector=select,
        )

        modality_payload: dict[str, object] = {}
        modality_lines: list[str] = []
        unit_for_modality = resolve_modelo_work_unit_for_operator_target(work_unit_id=selected_revision.work_unit_id)
        modality_summary = modelo_202_modality_for_work_unit(unit_for_modality)
        if modality_summary is not None:
            modality_payload = {
                "modality": modality_summary.modality,
                "modality_reason": modality_summary.reason,
            }
            modality_lines = [f"modality\t{modality_summary.modality}"]

        result = WorkRevisionResult.model_validate(
            {
                **calculation_revision_payload(selected_revision).model_dump(mode="python"),
                **modality_payload,
            },
        )
        lines = [
            "operation\tmodelo.work.revision",
            *calculation_revision_lines(selected_revision, verbose=verbose),
            *modality_lines,
        ]
        _emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


def _register_work_observations_command(work_app: typer.Typer, deps: _WorkRevisionCommandDeps) -> None:
    @work_app.command(
        "observations",
        help=tr(
            "cli.app.modelo.work.observations_help",
            default="Show typed per-casilla calculation observations and provenance.",
        ),
    )
    @command_execution_policy(MODEL_READ)
    def work_observations(
        ctx: typer.Context,
        calculation_revision_id: _CalculationRevisionIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        registry_revision: _RegistryRevisionOpt = None,
        work_unit_id: _WorkUnitIdOpt = None,
        select: _RevisionSelectorOpt = ModeloCalculationRevisionSelector.CURRENT.value,
        bucket_id: _BucketIdOpt = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Show observation provenance for one stored :class:`CalculationRevision`.

        The JSON branch emits
        :class:`ObservationPayload`
        rows through the observations result schema.
        """
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        selected_revision = _resolve_selected_revision(
            deps,
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=registry_revision,
            bucket_id=bucket_id,
            selector=select,
        )

        revision_payload = calculation_revision_payload(selected_revision)
        result = WorkObservationsResult.model_validate(
            {
                "calculation_revision_id": revision_payload.calculation_revision_id,
                "work_unit_id": revision_payload.work_unit_id,
                "state": revision_payload.state,
                "observation_count": len(revision_payload.observations),
                "observations": revision_payload.observations,
            },
        )
        lines = [
            "operation\tmodelo.work.observations",
            *calculation_observation_lines(selected_revision),
        ]
        _emit_envelope(ctx, command="modelo.work.observations", result=result, lines=lines)


def register_work_revision_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., WorkUnit],
    resolve_revision_for_cli: Callable[..., CalculationRevision],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    selector_bad_parameter: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register read-only calculation revision commands.

    Args:
        work_app: Typer sub-application that receives the commands.
        activate_output_language: CLI language activation hook.
        require_active_profile: Guard invoked before reading profile-scoped
            revision state.
        resolve_work_unit_for_cli: Resolver for visible work-unit targets.
        resolve_revision_for_cli: Resolver returning the selected
            :class:`CalculationRevision`.
        bad_parameter_from_error: Error adapter for direct revision-id failures.
        selector_bad_parameter: Error adapter for selector-based failures.
    """
    deps = _WorkRevisionCommandDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_revision_for_cli=resolve_revision_for_cli,
        bad_parameter_from_error=bad_parameter_from_error,
        selector_bad_parameter=selector_bad_parameter,
    )
    _register_work_revisions_command(work_app, deps)
    _register_work_revision_command(work_app, deps)
    _register_work_observations_command(work_app, deps)


__all__ = ["register_work_revision_commands"]
