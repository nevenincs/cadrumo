"""Typer registrations for modelo projection and comparison commands."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

import typer

from ...application.modelo import (
    ModeloCompareDeltaRow,
    ModeloCompareNeedTwoYearsError,
    ModeloCompareNoRevisionsError,
    ModeloCompareNoUsableRevisionsError,
    ModeloCompareNoWorkUnitsError,
    ModeloProjectInvalidDecimalOverrideError,
    ModeloProjectNoM130RevisionsError,
    ModeloProjectNoM130UnitsError,
    compare_modelo_years,
    project_modelo_100_from_m130,
)
from ...core import Modelo
from ...core.i18n import tr
from ...domain.calculations.registry import RegistrySnapshotError, RegistryValidationError
from ._common import _emit_envelope
from ._modelo_payloads import (
    CasillaObservationPayload,
    CompareSectionPayload,
    DeltaRowPayload,
    M100ProjectionPayload,
    M130AccumulatedPayload,
    ModeloCompareResult,
    ModeloProjectResult,
)

ParseOverride = Callable[[str], tuple[str, str]]
BadParameterRenderer = Callable[[BaseException], typer.BadParameter]


def register_projection_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    parse_casilla_override: ParseOverride,
    parse_binding_override: ParseOverride,
    bad_parameter_from_error: BadParameterRenderer,
    bad_parameter_from_localized_context: BadParameterRenderer,
) -> None:
    """Register projection commands against the root modelo Typer app."""
    _register_modelo_project_command(
        app,
        require_active_profile=require_active_profile,
        parse_casilla_override=parse_casilla_override,
        parse_binding_override=parse_binding_override,
        bad_parameter_from_error=bad_parameter_from_error,
        bad_parameter_from_localized_context=bad_parameter_from_localized_context,
    )
    _register_modelo_compare_command(
        app,
        require_active_profile=require_active_profile,
        bad_parameter_from_error=bad_parameter_from_error,
        bad_parameter_from_localized_context=bad_parameter_from_localized_context,
    )


def _register_modelo_project_command(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    parse_casilla_override: ParseOverride,
    parse_binding_override: ParseOverride,
    bad_parameter_from_error: BadParameterRenderer,
    bad_parameter_from_localized_context: BadParameterRenderer,
) -> None:
    @app.command(
        "project",
        help=tr(
            "cli.app.modelo.project_help",
            default=(
                "Project a year-end Modelo 100 from quarterly Modelo 130 filings. "
                "Reads all M130 work-unit revisions for --year, aggregates rendimiento neto "
                "and pagos fraccionados, and runs the M100 registry calculation to surface "
                "the projected cuota íntegra and net obligation."
            ),
        ),
    )
    def modelo_project(
        ctx: typer.Context,
        year: Annotated[
            int,
            typer.Option(
                "--year",
                help=tr("cli.app.modelo.project.year_help", default="Filing year (e.g. 2024)."),
            ),
        ],
        ccaa: Annotated[
            str,
            typer.Option(
                "--ccaa",
                help=tr(
                    "cli.app.modelo.project.ccaa_help",
                    default=(
                        "Autonomous community tax residence key for the M100 autonomic scale "
                        "(e.g. cataluna, comunidad-valenciana). Must match the registry enum."
                    ),
                ),
            ),
        ],
        casilla: Annotated[
            list[str] | None,
            typer.Option(
                "--casilla",
                help=tr(
                    "cli.app.modelo.project.casilla_help",
                    default=(
                        "Additional M100 casilla override as ID=VALUE (e.g. 0513=1150 for "
                        "age supplement). Repeat for multiple overrides."
                    ),
                ),
            ),
        ] = None,
        binding: Annotated[
            list[str] | None,
            typer.Option(
                "--binding",
                help=tr(
                    "cli.app.modelo.project.binding_help",
                    default=(
                        "Additional M100 binding override as KEY=VALUE. Repeat for multiple. "
                        "Retenciones bindings (renta-YYYY-modelo-111-retenciones-periodicas etc.) "
                        "default to zero when not supplied."
                    ),
                ),
            ),
        ] = None,
    ) -> None:
        """Project a year-end Modelo 100 from the active profile's M130 quarterly filings."""
        require_active_profile()
        casilla_pairs = dict(parse_casilla_override(spec) for spec in (casilla or ()))
        binding_pairs = dict(parse_binding_override(spec) for spec in (binding or ()))
        try:
            service_result = project_modelo_100_from_m130(
                year=year,
                ccaa=ccaa,
                casilla_overrides=casilla_pairs,
                binding_overrides=binding_pairs,
            )
        except (
            ModeloProjectNoM130UnitsError,
            ModeloProjectNoM130RevisionsError,
            ModeloProjectInvalidDecimalOverrideError,
        ) as exc:
            raise bad_parameter_from_localized_context(exc) from exc
        except RegistrySnapshotError as exc:
            raise bad_parameter_from_error(exc) from exc
        except RegistryValidationError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.project.m100_calculation_error",
                    default=f"M100 projection calculation failed: {exc}",
                ),
            ) from exc

        project_result = ModeloProjectResult(
            year=service_result.year,
            ccaa=service_result.ccaa,
            quarters_filed=service_result.quarters_filed,
            quarters_available=list(service_result.quarters_available),
            is_extrapolated=service_result.is_extrapolated,
            m130_accumulated=M130AccumulatedPayload(
                ingresos=str(service_result.m130_accumulated.ingresos),
                gastos=str(service_result.m130_accumulated.gastos),
                rendimiento_neto=str(service_result.m130_accumulated.rendimiento_neto),
                pagos_fraccionados=str(service_result.m130_accumulated.pagos_fraccionados),
            ),
            casilla_observations=[
                CasillaObservationPayload(
                    casilla_id=entry.casilla_id,
                    value=str(entry.value),
                    formula_id=entry.formula_id,
                    legal_refs=list(entry.legal_refs),
                    source_refs=list(entry.source_refs),
                )
                for entry in service_result.casilla_observations
            ],
            m100_projection=M100ProjectionPayload(
                base_liquidable_general_0505=str(service_result.m100_projection.base_liquidable_general_0505),
                pagos_fraccionados_0604=str(service_result.m100_projection.pagos_fraccionados_0604),
                cuota_integra_estatal_0545=str(service_result.m100_projection.cuota_integra_estatal_0545),
                cuota_integra_autonomica_0546=str(service_result.m100_projection.cuota_integra_autonomica_0546),
                cuota_liquida_estatal_0595=str(service_result.m100_projection.cuota_liquida_estatal_0595),
                cuota_liquida_autonomica_0596=str(service_result.m100_projection.cuota_liquida_autonomica_0596),
                cuota_resultante_0597=str(service_result.m100_projection.cuota_resultante_0597),
            ),
        )
        extrapolation_note = (
            f" (extrapolated from {service_result.quarters_filed}Q)" if service_result.is_extrapolated else ""
        )
        lines = [
            "operation\tmodelo.project",
            f"year\t{service_result.year}",
            f"ccaa\t{service_result.ccaa}",
            f"quarters_filed\t{service_result.quarters_filed}/4{extrapolation_note}",
            f"m130_ingresos\t{service_result.m130_accumulated.ingresos}",
            f"m130_gastos\t{service_result.m130_accumulated.gastos}",
            f"m130_rendimiento_neto\t{service_result.m130_accumulated.rendimiento_neto}",
            f"m130_pagos_fraccionados\t{service_result.m130_accumulated.pagos_fraccionados}",
            "---",
            f"m100_base_liquidable_general\t{service_result.m100_projection.base_liquidable_general_0505}",
            f"m100_cuota_integra_estatal\t{service_result.m100_projection.cuota_integra_estatal_0545}",
            f"m100_cuota_integra_autonomica\t{service_result.m100_projection.cuota_integra_autonomica_0546}",
            f"m100_cuota_liquida_estatal\t{service_result.m100_projection.cuota_liquida_estatal_0595}",
            f"m100_cuota_liquida_autonomica\t{service_result.m100_projection.cuota_liquida_autonomica_0596}",
            f"m100_cuota_resultante\t{service_result.m100_projection.cuota_resultante_0597}",
        ]
        _emit_envelope(ctx, command="modelo.project", result=project_result, lines=lines)


def _register_modelo_compare_command(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    bad_parameter_from_error: BadParameterRenderer,
    bad_parameter_from_localized_context: BadParameterRenderer,
) -> None:
    @app.command(
        "compare",
        help=tr(
            "cli.app.modelo.compare_help",
            default=(
                "Compare two filing-year calculation revisions for the same modelo. "
                "Emits per-casilla delta rows (year_b - year_a) grouped by section. "
                "Uses the most recent VERIFICADO_COMPLETO revision for each year; "
                "falls back to the latest BORRADOR when no verified revision exists, "
                "and flags the affected year as a draft in the output."
            ),
        ),
    )
    def modelo_compare(
        ctx: typer.Context,
        year: Annotated[
            list[int] | None,
            typer.Option(
                "--year",
                help=tr(
                    "cli.app.modelo.compare.year_help",
                    default=(
                        "Filing year to include in the comparison. Specify exactly twice: --year 2024 --year 2025."
                    ),
                ),
            ),
        ] = None,
        modelo: Annotated[
            str,
            typer.Option(
                "--modelo",
                help=tr(
                    "cli.app.modelo.compare.modelo_help",
                    default="Modelo number to compare (e.g. 100, 130).",
                ),
            ),
        ] = Modelo.M100.value,
    ) -> None:
        """Compare two filing-year revisions for the same modelo casilla-by-casilla."""
        require_active_profile()
        try:
            service_result = compare_modelo_years(modelo=modelo, years=list(year or ()))
        except (
            ModeloCompareNeedTwoYearsError,
            ModeloCompareNoWorkUnitsError,
            ModeloCompareNoRevisionsError,
            ModeloCompareNoUsableRevisionsError,
        ) as exc:
            raise bad_parameter_from_localized_context(exc) from exc
        except RegistrySnapshotError as exc:
            raise bad_parameter_from_error(exc) from exc

        typed_delta_rows = [_delta_row_payload(row) for row in service_result.delta_rows]
        typed_sections = [
            CompareSectionPayload(section=section.section, rows=[_delta_row_payload(row) for row in section.rows])
            for section in service_result.sections
        ]
        compare_result = ModeloCompareResult(
            modelo=service_result.modelo,
            year_a=service_result.year_a,
            year_b=service_result.year_b,
            year_a_revision_id=service_result.year_a_revision_id,
            year_b_revision_id=service_result.year_b_revision_id,
            year_a_is_draft=service_result.year_a_is_draft,
            year_b_is_draft=service_result.year_b_is_draft,
            sections=typed_sections,
            delta_rows=typed_delta_rows,
        )

        draft_note_a = " (BORRADOR)" if service_result.year_a_is_draft else ""
        draft_note_b = " (BORRADOR)" if service_result.year_b_is_draft else ""
        lines = [
            "operation\tmodelo.compare",
            f"modelo\t{service_result.modelo}",
            f"year_a\t{service_result.year_a}{draft_note_a}",
            f"year_b\t{service_result.year_b}{draft_note_b}",
            "---",
            "casilla_id\tlabel\tsection\tyear_a\tyear_b\tdelta\tpct_change",
        ]
        for row in service_result.delta_rows:
            if row.delta == Decimal("0") and row.year_a_value == Decimal("0") and row.year_b_value == Decimal("0"):
                continue
            pct = row.pct_change if row.pct_change is not None else "n/a"
            lines.append(
                f"{row.casilla_id}\t{row.label}\t{row.section}"
                f"\t{row.year_a_value}\t{row.year_b_value}\t{row.delta}\t{pct}",
            )
        _emit_envelope(ctx, command="modelo.compare", result=compare_result, lines=lines)


def _delta_row_payload(row: ModeloCompareDeltaRow) -> DeltaRowPayload:
    return DeltaRowPayload(
        casilla_id=row.casilla_id,
        label=row.label,
        section=row.section,
        year_a_value=str(row.year_a_value),
        year_b_value=str(row.year_b_value),
        delta=str(row.delta),
        pct_change=str(row.pct_change) if row.pct_change is not None else None,
        formula_id=row.formula_id,
        legal_refs=list(row.legal_refs),
        source_refs=list(row.source_refs),
    )


__all__ = ["register_projection_commands"]
