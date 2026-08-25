"""Behavior for modelo work :class:`CalculationRevision` read commands.

The graph-declared commands list stored calculation revisions, show one persisted
revision, and render its typed casilla observations without mutating modelo
state. Selection stays in the injected application-facing resolvers; this
transport module serializes results into
:class:`WorkRevisionsResult`,
:class:`WorkRevisionResult`,
and
:class:`WorkObservationsResult`
schemas before handing them to
:func:`emit_envelope`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import typer

from ...application.modelo._action_errors import CalculationRevisionNotFoundError
from ...application.modelo._calculate_input import modelo_202_modality_for_work_unit
from ...application.modelo._calculation_actions import list_calculation_revisions
from ...application.modelo._selectors import ModeloCalculationRevisionSelector
from ...core.external_constants import OutputLanguage
from ...domain.modelos import CalculationRevision, WorkUnit
from ._common import activate_subcommand_output_language, emit_envelope
from ._modelo_behavior_support import require_active_profile, resolve_revision_for_cli, resolve_work_unit_for_cli
from ._modelo_cli_support import bad_parameter_from_error, selector_bad_parameter
from ._modelo_payloads import (
    CalculationRevisionSummaryPayload,
    WorkObservationsResult,
    WorkRevisionResult,
    WorkRevisionsResult,
)
from ._modelo_rendering import (
    calculation_observation_lines,
    calculation_revision_lines,
    calculation_revision_payload,
    short_id,
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


def _revision_dependencies() -> _WorkRevisionCommandDeps:
    return _WorkRevisionCommandDeps(
        activate_output_language=activate_subcommand_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_revision_for_cli=resolve_revision_for_cli,
        bad_parameter_from_error=bad_parameter_from_error,
        selector_bad_parameter=selector_bad_parameter,
    )


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


__all__ = ["work_observations", "work_revision", "work_revisions"]


def work_revisions(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List persisted :class:`CalculationRevision` rows for an optional :class:`WorkUnit`."""
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    resolved_work_unit_id = work_unit_id
    if work_unit_id is not None or modelo is not None or year is not None or (period is not None):
        unit = resolve_work_unit_for_cli(
            work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
        )
        resolved_work_unit_id = unit.work_unit_id
    revisions = list_calculation_revisions(work_unit_id=resolved_work_unit_id)
    result = WorkRevisionsResult.model_validate(
        {
            "work_unit_id_filter": resolved_work_unit_id,
            "revision_count": len(revisions),
            "revisions": [
                CalculationRevisionSummaryPayload(
                    short_calculation_revision_id=short_id(rev.calculation_revision_id) or "",
                    calculation_revision_id=rev.calculation_revision_id,
                    short_work_unit_id=short_id(rev.work_unit_id) or "",
                    work_unit_id=rev.work_unit_id,
                    state=rev.state,
                    created_at=rev.created_at.isoformat(),
                )
                for rev in revisions
            ],
        }
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
            )
        )
        for rev in revisions
    )
    emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)


def work_revision(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    work_unit_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: str | None = None,
    verbose: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show one selected :class:`CalculationRevision` as a work-revision result.

    The JSON branch emits
    :class:`WorkRevisionResult`.
    Each computed casilla renders its formula trace inline as
    ``op(refs) = op(values) = value``; ``--verbose`` additionally surfaces
    the full operand lineage line beneath each computed row.
    """
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    selected_revision = _resolve_selected_revision(
        _revision_dependencies(),
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
    unit_for_modality = resolve_work_unit_for_cli(work_unit_id=selected_revision.work_unit_id)
    modality_summary = modelo_202_modality_for_work_unit(unit_for_modality)
    if modality_summary is not None:
        modality_payload = {"modality": modality_summary.modality, "modality_reason": modality_summary.reason}
        modality_lines = [f"modality\t{modality_summary.modality}"]
    result = WorkRevisionResult.model_validate(
        {**calculation_revision_payload(selected_revision).model_dump(mode="python"), **modality_payload}
    )
    lines = [
        "operation\tmodelo.work.revision",
        *calculation_revision_lines(selected_revision, verbose=verbose),
        *modality_lines,
    ]
    emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


def work_observations(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    work_unit_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show observation provenance for one stored :class:`CalculationRevision`.

    The JSON branch emits
    :class:`ObservationPayload`
    rows through the observations result schema.
    """
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    selected_revision = _resolve_selected_revision(
        _revision_dependencies(),
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
        }
    )
    lines = ["operation\tmodelo.work.observations", *calculation_observation_lines(selected_revision)]
    emit_envelope(ctx, command="modelo.work.observations", result=result, lines=lines)
