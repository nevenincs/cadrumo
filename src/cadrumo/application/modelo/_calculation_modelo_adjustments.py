"""Modelo-specific adjustment helpers for calculation actions.

These private helpers keep model-specific edge cases out of the generic
calculation action path: M131 fixed-record data-base projections, M390/M303
cross-period reconciliation refusal, and M349 row-template/display suppression.
They operate on the already resolved registry snapshot and preserve the typed
observation contract that the calculation action persists.

See Also:
    :func:`~application.modelo.calculate_modelo_revision`
        Application calculation action that calls these adjustment helpers.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry engine whose output is adjusted before persistence.
    :class:`~domain.calculations.registry.RegistrySnapshot`
        Law-determined snapshot used for relation and period requirements.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision whose export layouts, bindings, and relations drive the
        model-specific adjustments.
    :class:`~domain.calculations.registry.CasillaObservation`
        Provenance-bearing observation rows filtered with M349 template fields.
    :class:`~domain.modelos.WorkUnit`
        Modelo, filing year, and period context selecting each adjustment.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core import Modelo
from ...core.aggregation import BindingSourceKind
from ...core.decimal import coerce_decimal_strict
from ...core.money import round_to_cents
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    CasillaObservation,
    ModeloRevision,
    RegistrySnapshot,
    RelationId,
    relation_source_requirements,
    selector_as_dict,
)
from ...domain.modelos import (
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    WorkUnit,
)
from ._action_errors import ModeloCrossPeriodCleanStateError

_M349_NUMERO_OPERADORES_BINDING: BindingId = "iva-349-declarante-numero-operadores"
_M349_IMPORTE_OPERACIONES_BINDING: BindingId = "iva-349-declarante-importe-operaciones"
_M349_NUMERO_RECTIFICACIONES_BINDING: BindingId = "iva-349-declarante-numero-rectificaciones"
_M349_IMPORTE_RECTIFICACIONES_BINDING: BindingId = "iva-349-declarante-importe-rectificaciones"
_ZERO = Decimal("0")
_M390_ANNUAL_PERIOD_CODE = "0A"
_M131_DATA_BASE_RENDIMIENTO_CASILLA: CasillaId = "01"
_M131_DATA_BASE_PAGO_PREVIO_CASILLA: CasillaId = "02"
_M131_PAGE1_ACTIVITY_FIELD_RE = re.compile(
    r"^actividad-(?P<index>[1-5])-(?P<kind>rendimiento-neto|porcentaje|resultado)$",
)
_M131_DPA_MODULE_RENDIMIENTO_RE = re.compile(r"^modulo-(?P<index>[1-7])-rendimiento-neto$")
_M390_303_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE: Mapping[CasillaId, CasillaId] = {
    "iva.cuota-devengada-total": "iva.anual.cuota-devengada-total",
    "iva.cuota-deducible-total": "iva.anual.cuota-deducible-total",
    "iva.resultado-regimen-general": "iva.anual.resultado-regimen-general",
}


@dataclass(frozen=True, slots=True)
class _M131ActivityInputs:
    rendimiento: Decimal | None = None
    porcentaje: Decimal | None = None
    resultado: Decimal | None = None


def _m131_objective_estimation_data_base_inputs(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project M131 page-1/DPA datos-base fixed-record bindings into liquidation inputs."""
    if str(work_unit.modelo) != Modelo.M131.value:
        return {}

    page1_rows: dict[str, _M131ActivityInputs] = {}
    dpa_rendimientos: list[Decimal] = []
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.MANUAL_INPUT or binding.id not in binding_values:
            continue
        selector = selector_as_dict(binding)
        record = selector.get("record")
        field = selector.get("field")
        if not isinstance(record, str) or not isinstance(field, str):
            continue
        value = binding_values[binding.id]
        if record == "page_1":
            match = _M131_PAGE1_ACTIVITY_FIELD_RE.match(field)
            if match is None:
                continue
            index = match.group("index")
            current = page1_rows.get(index, _M131ActivityInputs())
            match match.group("kind"):
                case "rendimiento-neto":
                    page1_rows[index] = _M131ActivityInputs(
                        rendimiento=value,
                        porcentaje=current.porcentaje,
                        resultado=current.resultado,
                    )
                case "porcentaje":
                    page1_rows[index] = _M131ActivityInputs(
                        rendimiento=current.rendimiento,
                        porcentaje=value,
                        resultado=current.resultado,
                    )
                case "resultado":
                    page1_rows[index] = _M131ActivityInputs(
                        rendimiento=current.rendimiento,
                        porcentaje=current.porcentaje,
                        resultado=value,
                    )
                case _:
                    pass
            continue
        if record == "DPA" and _M131_DPA_MODULE_RENDIMIENTO_RE.match(field) is not None:
            dpa_rendimientos.append(value)

    projected: dict[CasillaId, Decimal] = {}
    page1_rendimientos = [row.rendimiento for row in page1_rows.values() if row.rendimiento is not None]
    if page1_rendimientos:
        projected[_M131_DATA_BASE_RENDIMIENTO_CASILLA] = sum(page1_rendimientos, Decimal("0"))
    elif dpa_rendimientos:
        projected[_M131_DATA_BASE_RENDIMIENTO_CASILLA] = sum(dpa_rendimientos, Decimal("0"))

    page1_results: list[Decimal] = []
    for row in page1_rows.values():
        if row.resultado is not None:
            page1_results.append(row.resultado)
        elif row.rendimiento is not None and row.porcentaje is not None:
            page1_results.append(round_to_cents(row.rendimiento * row.porcentaje / Decimal("100")))
    if page1_results:
        projected[_M131_DATA_BASE_PAGO_PREVIO_CASILLA] = sum(page1_results, Decimal("0"))
    return projected


def _m349_row_field_template_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    return frozenset(
        casilla_id
        for export_layout in revision.export_layouts
        for record in export_layout.records
        for casilla_id in record.row_field_casilla_ids.values()
    )


def _calculated_decimal(value: object | None) -> Decimal:
    if value is None:
        return _ZERO
    return coerce_decimal_strict(value)


def _m390_303_reconciliation_targets(
    snapshot: RegistrySnapshot,
) -> tuple[tuple[RelationId, BindingId, CasillaId, CasillaId, CasillaId], ...]:
    """Return M390 reconciliation relation targets keyed by their M303 source output."""
    target_casillas_by_binding = {
        casilla.binding: casilla.id for casilla in snapshot.revision.casillas if casilla.binding is not None
    }
    targets: list[tuple[RelationId, BindingId, CasillaId, CasillaId, CasillaId]] = []
    for relation in snapshot.revision.relations:
        if relation.source_modelo != Modelo.M303.value:
            continue
        annual_casilla = _M390_303_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE.get(relation.source_casilla_id)
        if annual_casilla is None:
            continue
        target_casilla = target_casillas_by_binding.get(relation.target_binding)
        if target_casilla is None:
            continue
        target = relation.id, relation.target_binding, target_casilla, relation.source_casilla_id, annual_casilla
        targets.append(target)
    return tuple(targets)


def _m390_303_required_periods(snapshot: RegistrySnapshot, relation_ids: frozenset[RelationId]) -> tuple[str, ...]:
    periods: set[str] = set()
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if relation_ids.intersection(requirement.relation_ids):
            periods.update(requirement.periods)
    return tuple(sorted(periods))


def _raise_if_m390_303_reconciliation_would_save_silent_zero(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
) -> None:
    """Refuse an M390 draft that would save zero 303 reconciliation slots from missing fold-in evidence."""
    if str(work_unit.modelo) != Modelo.M390.value or work_unit.period.registry_token != _M390_ANNUAL_PERIOD_CODE:
        return

    missing: list[tuple[RelationId, BindingId, CasillaId, CasillaId]] = []
    for relation_id, binding_id, target_casilla, _source_casilla, annual_casilla in _m390_303_reconciliation_targets(
        snapshot,
    ):
        if binding_id in resolved_binding_values:
            continue
        if _calculated_decimal(casilla_values.get(annual_casilla)) == _ZERO:
            continue
        missing.append((relation_id, binding_id, target_casilla, annual_casilla))

    if not missing:
        return

    missing_relation_ids = frozenset(relation_id for relation_id, _binding_id, _target, _annual in missing)
    raise ModeloCrossPeriodCleanStateError(
        (
            "Modelo 390 calculation refused: nonzero annual IVA totals are present, "
            "but the Modelo 303 reconciliation bindings did not resolve from clean "
            "current quarterly filing observations."
        ),
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": len(missing),
            "reason": "missing_clean_cross_period_303_filings_or_observations",
            "missing_303_periods": _m390_303_required_periods(snapshot, missing_relation_ids),
            "missing_303_reconciliation_bindings": tuple(binding_id for _rel, binding_id, _target, _annual in missing),
            "zero_reconciliation_casillas_at_risk": tuple(target for _rel, _binding, target, _annual in missing),
            "nonzero_annual_casillas": tuple(annual for _rel, _binding, _target, annual in missing),
        },
        suggestion="aeat app live filed pull-sources --modelo 303",
    )


def _suppress_m349_row_field_template_outputs(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    casilla_values: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
) -> tuple[dict[CasillaId, Decimal], tuple[CasillaObservation, ...]]:
    if str(work_unit.modelo) != Modelo.M349.value:
        return casilla_values, observations
    row_field_casilla_ids = _m349_row_field_template_casilla_ids(revision)
    if not row_field_casilla_ids:
        return casilla_values, observations
    return (
        {casilla_id: value for casilla_id, value in casilla_values.items() if casilla_id not in row_field_casilla_ids},
        tuple(observation for observation in observations if observation.casilla_id not in row_field_casilla_ids),
    )


def _detail_row_binding_values_for_calculation(
    *,
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> dict[BindingId, Decimal]:
    if str(work_unit.modelo) != Modelo.M349.value:
        return {}
    operador_rows = tuple(row for row in detail_rows if isinstance(row, Modelo349OperadorRow))
    rectification_rows = tuple(row for row in detail_rows if isinstance(row, Modelo349RectificacionRow))
    if not operador_rows and not rectification_rows:
        return {}
    importe_operaciones = sum((row.importe for row in operador_rows), Decimal("0"))
    importe_rectificaciones = sum(
        (abs(row.base_rectificada - row.base_anterior) for row in rectification_rows),
        Decimal("0"),
    )
    return {
        _M349_NUMERO_OPERADORES_BINDING: Decimal(len(operador_rows)),
        _M349_IMPORTE_OPERACIONES_BINDING: importe_operaciones,
        _M349_NUMERO_RECTIFICACIONES_BINDING: Decimal(len(rectification_rows)),
        _M349_IMPORTE_RECTIFICACIONES_BINDING: importe_rectificaciones,
    }


calculated_decimal = _calculated_decimal
detail_row_binding_values_for_calculation = _detail_row_binding_values_for_calculation
m131_objective_estimation_data_base_inputs = _m131_objective_estimation_data_base_inputs
raise_if_m390_303_reconciliation_would_save_silent_zero = _raise_if_m390_303_reconciliation_would_save_silent_zero
suppress_m349_row_field_template_outputs = _suppress_m349_row_field_template_outputs
