"""Behavior handlers for modelo projection and comparison commands.

The ``modelo.project`` adapter calls :func:`project_modelo_100_from_m130`
and serializes the service result as :class:`ModeloProjectResult`.  Its
:class:`CasillaObservationPayload` list is the provenance-carrying channel for
formula-computed :class:`CasillaId` values, while
:class:`M130AccumulatedPayload` and :class:`M100ProjectionPayload` expose the
operator-facing summary values.

The ``modelo.compare`` adapter calls :func:`compare_modelo_years`, converts
:class:`ModeloCompareDeltaRow` rows into :class:`DeltaRowPayload`, and emits the
typed envelope through :func:`emit_envelope`.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

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
from ...core import CasillaId, Modelo
from ...core.output_rendering import jsonable_output_payload
from ...domain.calculations.registry import RegistrySnapshotError, RegistryValidationError
from ._common import emit_envelope
from ._modelo_behavior_support import require_active_profile
from ._modelo_cli_support import (
    bad_parameter_from_error,
    bad_parameter_from_localized_context,
    parse_binding_override,
    parse_casilla_override,
)
from ._modelo_payloads import (
    CasillaObservationPayload,
    CompareSectionPayload,
    DeltaRowPayload,
    M100ProjectionPayload,
    M130AccumulatedPayload,
    ModeloCompareResult,
    ModeloProjectResult,
)

CasillaParseOverride = Callable[[str], tuple[CasillaId, str]]
BindingParseOverride = Callable[[str], tuple[str, str]]
BadParameterRenderer = Callable[[BaseException], typer.BadParameter]


def _delta_row_payload(row: ModeloCompareDeltaRow) -> DeltaRowPayload:
    """Convert one :class:`ModeloCompareDeltaRow` into :class:`DeltaRowPayload`.

    The adapter preserves :class:`CasillaId` identity and registry provenance so
    the :class:`ModeloCompareResult` envelope mirrors :func:`compare_modelo_years`.
    """
    return DeltaRowPayload(
        casilla_id=row.casilla_id,
        label=row.label,
        section=row.section,
        year_a_value=_decimal_wire(row.year_a_value),
        year_b_value=_decimal_wire(row.year_b_value),
        delta=_decimal_wire(row.delta),
        pct_change=_decimal_wire(row.pct_change) if row.pct_change is not None else None,
        formula_id=row.formula_id,
        legal_refs=list(row.legal_refs),
        source_refs=list(row.source_refs),
    )


def _decimal_wire(value: Decimal) -> str:
    """Render a Decimal through the CLI's canonical JSON normalization authority."""
    rendered = jsonable_output_payload(value)
    if not isinstance(rendered, str):
        raise TypeError(f"CLI Decimal normalization returned {type(rendered).__name__}, not str")
    return rendered


__all__ = ["modelo_compare", "modelo_project", "require_active_profile"]


def modelo_project(
    ctx: typer.Context, year: int, ccaa: str, casilla: list[str] | None = None, binding: list[str] | None = None
) -> None:
    """Emit :class:`ModeloProjectResult` from active-profile M130 filings.

    The application service returns typed projection observations; this CLI
    command maps each one to :class:`CasillaObservationPayload` so
    ``formula_id``, ``legal_refs``, and ``source_refs`` remain attached
    before :func:`emit_envelope` renders JSON or table output.
    """
    require_active_profile()
    casilla_pairs = dict(parse_casilla_override(spec) for spec in casilla or ())
    binding_pairs = dict(parse_binding_override(spec) for spec in binding or ())
    try:
        service_result = project_modelo_100_from_m130(
            year=year, ccaa=ccaa, casilla_overrides=casilla_pairs, binding_overrides=binding_pairs
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
        raise bad_parameter_from_error(exc) from exc
    project_result = ModeloProjectResult(
        year=service_result.year,
        ccaa=service_result.ccaa,
        quarters_filed=service_result.quarters_filed,
        quarters_available=list(service_result.quarters_available),
        is_extrapolated=service_result.is_extrapolated,
        m130_accumulated=M130AccumulatedPayload(
            ingresos=_decimal_wire(service_result.m130_accumulated.ingresos),
            gastos=_decimal_wire(service_result.m130_accumulated.gastos),
            rendimiento_neto=_decimal_wire(service_result.m130_accumulated.rendimiento_neto),
            pagos_fraccionados=_decimal_wire(service_result.m130_accumulated.pagos_fraccionados),
        ),
        casilla_observations=[
            CasillaObservationPayload(
                casilla_id=entry.casilla_id,
                value=_decimal_wire(entry.value),
                formula_id=entry.formula_id,
                legal_refs=list(entry.legal_refs),
                source_refs=list(entry.source_refs),
            )
            for entry in service_result.casilla_observations
        ],
        m100_projection=M100ProjectionPayload(
            base_liquidable_general_0505=_decimal_wire(service_result.m100_projection.base_liquidable_general_0505),
            pagos_fraccionados_0604=_decimal_wire(service_result.m100_projection.pagos_fraccionados_0604),
            cuota_integra_estatal_0545=_decimal_wire(service_result.m100_projection.cuota_integra_estatal_0545),
            cuota_integra_autonomica_0546=_decimal_wire(service_result.m100_projection.cuota_integra_autonomica_0546),
            cuota_liquida_estatal_0595=_decimal_wire(service_result.m100_projection.cuota_liquida_estatal_0595),
            cuota_liquida_autonomica_0596=_decimal_wire(service_result.m100_projection.cuota_liquida_autonomica_0596),
            cuota_resultante_0597=_decimal_wire(service_result.m100_projection.cuota_resultante_0597),
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
    emit_envelope(ctx, command="modelo.project", result=project_result, lines=lines)


def modelo_compare(ctx: typer.Context, year: list[int] | None = None, modelo: str = Modelo.M100.value) -> None:
    """Emit :class:`ModeloCompareResult` with grounded delta rows.

    Each service row arrives as :class:`ModeloCompareDeltaRow`; the CLI
    schema preserves ``formula_id``, ``legal_refs``, and ``source_refs`` for
    every compared :class:`CasillaId`.
    """
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
        if row.delta == Decimal("0") and row.year_a_value == Decimal("0") and (row.year_b_value == Decimal("0")):
            continue
        pct = row.pct_change if row.pct_change is not None else "n/a"
        lines.append(
            f"{row.casilla_id}\t{row.label}\t{row.section}\t{row.year_a_value}\t{row.year_b_value}\t{row.delta}\t{pct}"
        )
    emit_envelope(ctx, command="modelo.compare", result=compare_result, lines=lines)
