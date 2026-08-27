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
from typing import get_args

from ...core import ActionEvidenceProvenance, CasillaId, Modelo
from ...core.aggregation import BindingSourceKind
from ...core.decimal import coerce_decimal_strict
from ...core.money import round_to_cents
from ...domain.calculations.registry.binding_selector_utils import manual_input_record_field_selector
from ...domain.calculations.registry.bindings import (
    CasillaObservation,
    casillas_by_binding,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.relations import relation_source_requirements
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.modelos import (
    Modelo184MemberRow,
    Modelo210AgrupacionRentaRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    ModeloError,
    WorkUnit,
)
from ._action_errors import ModeloAggregationBindingError, ModeloCrossPeriodCleanStateError
from ._preconditions import build_modelo_precondition_failure

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

_DETAIL_ROW_OWNING_MODELO: Mapping[type[ModeloDetailRow], str] = {
    Modelo184MemberRow: "184",
    Modelo232VinculadaRow: "232",
    Modelo349OperadorRow: "349",
    Modelo349RectificacionRow: "349",
    Modelo347ContraparteRow: "347",
    Modelo210AgrupacionRentaRow: "210",
}


def require_detail_rows_declared_for_their_owning_modelo(
    *,
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Refuse any detail row whose typed kind belongs to a different modelo.

    Each ``ModeloDetailRow`` subtype is a bespoke per-modelo shape (M184
    member, M232 vinculada, M349 operador/rectificación, M347 contraparte,
    M210 agrupación renta) that is never legitimately declared against a
    different modelo's work unit. Before this check existed, a mismatched
    row was silently PERSISTED into that revision's ``detail_rows`` while
    contributing to no figure -- a taxpayer-declared row that appeared to
    exist yet affected nothing, with no advisory anywhere. Every kind now
    refuses through one convention rather than five ad hoc call sites.

    This runs at the calculate boundary's single funnel
    (:func:`~._calculation_actions._calculate_modelo_revision_with_trusted_mesh_sources`),
    so both the direct and bucket-aggregation calculate entry points are
    covered.
    """
    for row in detail_rows:
        owning_modelo = _DETAIL_ROW_OWNING_MODELO.get(type(row))
        if owning_modelo is None or str(work_unit.modelo) == owning_modelo:
            continue
        raise ModeloError(
            translated_message="errors.error.error_modelo_detail_row_wrong_modelo",
            context={
                "row_type": type(row).__name__,
                "owning_modelo": owning_modelo,
                "work_unit_modelo": str(work_unit.modelo),
            },
        )


#: Each detail-row kind's own natural real-world identity -- the field tuple
#: that names WHICH counterparty/operation/member a row is about, as distinct
#: from the declarable figures (amounts, percentages) that describe it. Two
#: rows sharing this key from different supply paths (a resolver and a
#: caller) name the SAME real-world thing and must union rather than
#: double-count; two rows sharing it that disagree on a declarable figure are
#: a genuine conflict, not a duplicate.
_ROW_IDENTITY_FIELDS: Mapping[type[ModeloDetailRow], tuple[str, ...]] = {
    Modelo184MemberRow: ("nif", "clave", "subclave"),
    Modelo232VinculadaRow: ("nif", "tipo_operacion"),
    Modelo347ContraparteRow: ("nif", "clave_operacion"),
    Modelo349OperadorRow: ("nif_comunitario", "clave_operacion"),
    Modelo349RectificacionRow: ("nif_comunitario", "clave_operacion", "ejercicio", "periodo"),
    Modelo210AgrupacionRentaRow: ("source_id",),
}


def _uncovered_row_kinds(covered: Mapping[type, tuple[str, ...]]) -> frozenset[type]:
    """Pure comparison: every ``ModeloDetailRow`` union member absent from ``covered``."""
    return frozenset(get_args(ModeloDetailRow)) - frozenset(covered)


def uncovered_detail_row_kinds() -> frozenset[type]:
    """Return every concrete ``ModeloDetailRow`` member absent from the identity table.

    Discovered from ``ModeloDetailRow`` itself -- the discriminated union's
    own member list -- rather than a hand-listed set, so a new row kind
    added to the union without a matching :data:`_ROW_IDENTITY_FIELDS` entry
    is caught by construction. Absence from the table is a silent regression
    of the fix: :func:`_row_identity` falls back to an identity-unique
    key for an uncovered kind, which never wrongly merges two distinct rows
    (the safe direction) but also never unions a genuine cross-path
    duplicate for that kind (the fix's whole purpose, silently un-done).
    """
    return _uncovered_row_kinds(_ROW_IDENTITY_FIELDS)


def _row_identity(row: ModeloDetailRow) -> tuple[object, ...]:
    fields = _ROW_IDENTITY_FIELDS.get(type(row))
    if fields is None:
        # An undeclared row kind has no known identity to union by; treat it
        # as identity-unique so it never collides (owning-modelo validation
        # elsewhere refuses genuinely unknown kinds).
        return (id(row),)
    return tuple(getattr(row, field) for field in fields)


def union_detail_rows_by_identity(
    *,
    resolver_rows: tuple[ModeloDetailRow, ...],
    caller_rows: tuple[ModeloDetailRow, ...],
) -> tuple[ModeloDetailRow, ...]:
    """Union resolver-produced and caller-supplied detail rows by identity.

    Naive concatenation double-counts a row two supply paths both name --
    an invoice-derived M349 operador row the operator also enters manually,
    for instance -- inflating every downstream count and sum derived from
    the row set. Rows are grouped by (row type, natural identity); a group
    fed by only one path passes through unchanged. A group fed by BOTH
    paths unions to the resolver's row when every remaining field (the
    declarable figures) agrees, and REFUSES, naming the identity and the
    divergent fields, when they disagree -- an unstated precedence pick
    between two supply paths on a filing-grade value is not this function's
    call to make.

    Two same-path rows sharing an identity (two caller rows, or two
    resolver rows) are left as duplicates for the caller to see: this
    function's contract is cross-path union, not intra-path deduplication,
    which is a different defect with a different owner.
    """
    if not resolver_rows or not caller_rows:
        return (*resolver_rows, *caller_rows)
    resolver_by_identity: dict[tuple[str, tuple[object, ...]], ModeloDetailRow] = {
        (row.row_type, _row_identity(row)): row for row in resolver_rows
    }
    unioned: list[ModeloDetailRow] = list(resolver_rows)
    for caller_row in caller_rows:
        key = (caller_row.row_type, _row_identity(caller_row))
        resolver_row = resolver_by_identity.get(key)
        if resolver_row is None:
            unioned.append(caller_row)
            continue
        if resolver_row == caller_row:
            continue
        divergent_fields = tuple(
            sorted(
                field
                for field in type(resolver_row).model_fields
                if getattr(resolver_row, field) != getattr(caller_row, field)
            ),
        )
        raise ModeloAggregationBindingError(
            translated_message="errors.error.error_modelo_aggregation_binding",
            context={
                "reason": "detail_row_identity_conflict",
                "row_type": caller_row.row_type,
                "identity": [str(component) for component in _row_identity(caller_row)],
                "divergent_fields": list(divergent_fields),
            },
        )
    return tuple(unioned)


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
        # Distinguishes the record-field manual_input shape (what this loop
        # projects) from the casilla shape (a real, different manual_input
        # selector this loop is not asked about) via the typed model, rather
        # than a raw selector.get("record") whose None default cannot tell a
        # legitimately-absent field from a mistyped one. A malformed selector
        # raises here instead of being silently treated as casilla-shape.
        manual_selector = manual_input_record_field_selector(binding)
        if manual_selector is None:
            continue
        record = manual_selector.record
        field = manual_selector.field
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
) -> tuple[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId], ...]:
    """Return M390 reconciliation relation targets keyed by their M303 source output."""
    target_casillas_by_binding = casillas_by_binding(snapshot.revision)
    targets: list[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId]] = []
    for relation in snapshot.revision.relations:
        if relation.source_modelo != Modelo.M303.value:
            continue
        annual_casilla = _M390_303_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE.get(relation.source_casilla_id)
        if annual_casilla is None:
            continue
        target_casillas = target_casillas_by_binding.get(relation.target_binding, ())
        if not target_casillas:
            continue
        target = relation.id, relation.target_binding, target_casillas, relation.source_casilla_id, annual_casilla
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

    missing_relations: list[RelationId] = []
    missing_bindings: list[BindingId] = []
    missing_targets: list[CasillaId] = []
    missing_annuals: list[CasillaId] = []
    for relation_id, binding_id, target_casillas, _source_casilla, annual_casilla in _m390_303_reconciliation_targets(
        snapshot,
    ):
        if binding_id in resolved_binding_values:
            continue
        if _calculated_decimal(casilla_values.get(annual_casilla)) == _ZERO:
            continue
        missing_relations.append(relation_id)
        missing_bindings.append(binding_id)
        missing_targets.extend(target_casillas)
        missing_annuals.append(annual_casilla)

    if not missing_bindings:
        return

    missing_periods = _m390_303_required_periods(snapshot, frozenset(missing_relations))
    raise ModeloCrossPeriodCleanStateError(
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": len(missing_bindings),
            "reason": "missing_clean_cross_period_303_filings_or_observations",
            "missing_303_periods": missing_periods,
            "missing_303_reconciliation_bindings": tuple(missing_bindings),
            "zero_reconciliation_casillas_at_risk": tuple(missing_targets),
            "nonzero_annual_casillas": tuple(missing_annuals),
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.m390.reconciliation.complete",
            scenario_id="modelo.work.calculate.m390.reconciliation.clean_m303_observations_missing",
            evidence_id="modelo.work.calculate.m390.reconciliation",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "missing_item_count": len(missing_bindings),
                "missing_periods": "|".join(missing_periods),
                "missing_binding_ids": "|".join(missing_bindings),
                "target_casilla_ids": "|".join(missing_targets),
                "annual_casilla_ids": "|".join(missing_annuals),
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        ),
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
