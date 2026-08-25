"""Layout planner mapping every casilla, binding, and parameter onto a Sheets cell address.

Operates on a :class:`ModeloRevision`.

The mapping is a pure function of the revision (and an optional
filing date for temporal bracket filtering). Two engine runs over
the same revision yield the same layout, and the pull adapter can
therefore round-trip a workbook back into casilla-id space without
consulting the source registry at runtime.

Layout strategy
---------------

- The `Entradas` tab lists every operator-input casilla (input_kind
  in {"manual", "bound", "informational"}). Each row carries
  `{section, display_number, label, value}` with the value cell
  anchored in column D. Bindings the formulas reference appear in
  their own rows below the casilla rows so the operator can review
  and override pre-resolved values.
- The `Cálculos` tab lists every computed casilla. Each row carries
  `{section, display_number, label, formula_value}` with the formula
  cell anchored in column D.
- The `Tarifas` tab mirrors every parameter referenced (directly or
  via a `lookup_bracket_by_ccaa` dispatch table) by a computed
  casilla's formula expression. Scalar parameters occupy a single
  cell; `bracket_table` parameters occupy a header row plus one row
  per temporally-active bracket entry.

Bracket tables filter out entries that are not valid on the supplied
`bracket_filter_date` so the row sequence emitted to `Tarifas`
matches the runtime's `_resolve_bracket` selection exactly. That
keeps `MATCH(_, lower_bound, 1)` honest in the translator's
closed-form `lookup_bracket` expansion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import CasillaId
from ....domain.calculations.registry import (
    BindingId,
    BracketEntry,
    CasillaDefinition,
    InputKind,
    ModeloRevision,
    ParameterDefinition,
    ParameterId,
    RelationId,
    RevisionId,
    expression_binding_refs,
    expression_date_binding_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from .errors import CalcSheetsEngineError
from ._records import (
    ParameterCell,
    SheetCellAddress,
    TabName,
    column_index_to_letters,
)


class _CasillaRow(BaseModel):
    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    tab: Literal[TabName.ENTRADAS, TabName.CALCULOS]
    row: int = Field(ge=2)
    section_path: tuple[str, ...]


class _BindingRow(BaseModel):
    model_config = _STRICT_FROZEN

    binding: BindingId
    tab: Literal[TabName.ENTRADAS]
    row: int = Field(ge=2)
    label: str


class BracketRanges(BaseModel):
    """A1 ranges for the lower-bound, fixed-addition, and marginal-rate columns of one bracket-table parameter.

    These ranges occupy the ``Tarifas`` tab. The translator's ``lookup_bracket`` handler resolves a
    bracket lookup against them via:

        INDEX(fixed_addition, MATCH(base, lower_bound, 1))
        + INDEX(marginal_rate, MATCH(base, lower_bound, 1))
        * (base - INDEX(lower_bound, MATCH(base, lower_bound, 1)))

    The ranges always hold one row per bracket entry that is
    temporally active for the snapshot's filing date — out-of-window
    entries are filtered before layout so the sort-1 `MATCH` contract
    stays clean.
    """

    model_config = _STRICT_FROZEN

    parameter: ParameterId
    lower_bound: str = Field(min_length=2)
    fixed_addition: str = Field(min_length=2)
    marginal_rate: str = Field(min_length=2)
    row_count: int = Field(ge=1)


class SheetLayout(BaseModel):
    """Resolved cell addresses for every casilla, binding, and parameter."""

    model_config = _STRICT_FROZEN

    revision_id: RevisionId
    entradas_cells: Mapping[CasillaId, SheetCellAddress]
    calculos_cells: Mapping[CasillaId, SheetCellAddress]
    binding_cells: Mapping[BindingId, SheetCellAddress]
    date_binding_cells: Mapping[BindingId, SheetCellAddress] = Field(default_factory=dict)
    filing_year: int = 0
    parameter_cells: Mapping[ParameterId, ParameterCell]
    relation_cells: Mapping[RelationId, SheetCellAddress]
    entradas_rows: tuple[_CasillaRow, ...]
    calculos_rows: tuple[_CasillaRow, ...]
    binding_rows: tuple[_BindingRow, ...]
    tariff_anchors: Mapping[ParameterId, SheetCellAddress]
    bracket_ranges: Mapping[ParameterId, BracketRanges]
    bracket_entries: Mapping[ParameterId, tuple[BracketEntry, ...]]

    def address_for(self, casilla_id: CasillaId) -> SheetCellAddress:
        """Resolve a casilla reference to the :class:`SheetCellAddress` holding its value.

        Computed casillas resolve to their ``Calculos`` cell; input
        casillas resolve to their ``Entradas`` cell. The translator uses
        this to compile a ``FormulaExpression`` casilla leaf into an A1
        reference.
        """
        if casilla_id in self.calculos_cells:
            return self.calculos_cells[casilla_id]
        if casilla_id in self.entradas_cells:
            return self.entradas_cells[casilla_id]
        raise _unknown_layout_reference("casilla")

    def address_for_binding(self, binding: BindingId) -> SheetCellAddress:
        if binding not in self.binding_cells:
            raise _unknown_layout_reference("binding")
        return self.binding_cells[binding]

    def address_for_date_binding(self, binding: BindingId) -> SheetCellAddress:
        if binding not in self.date_binding_cells:
            raise _unknown_layout_reference("date_binding")
        return self.date_binding_cells[binding]

    def address_for_relation(self, relation: RelationId) -> SheetCellAddress:
        if relation not in self.relation_cells:
            raise _unknown_layout_reference("relation")
        return self.relation_cells[relation]


def _unknown_layout_reference(reference_kind: str) -> CalcSheetsEngineError:
    return CalcSheetsEngineError(
        "layout reference has no resolved cell",
        context={"reference_kind": reference_kind},
        translated_message="application.storage.calc_sheets.layout.errors.unresolved_reference",
    )


def _undeclared_layout_reference(reference_kind: str) -> CalcSheetsEngineError:
    return CalcSheetsEngineError(
        "layout reference is not declared by the revision",
        context={"reference_kind": reference_kind},
        translated_message="application.storage.calc_sheets.layout.errors.undeclared_reference",
    )


def _referenced_date_bindings(revision: ModeloRevision) -> tuple[BindingId, ...]:
    seen: dict[BindingId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for binding in expression_date_binding_refs(formula.expression):
            seen.setdefault(binding, None)
    return tuple(seen)


def _referenced_relations(revision: ModeloRevision) -> tuple[RelationId, ...]:
    seen: dict[RelationId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for relation in expression_relation_refs(formula.expression):
            seen.setdefault(relation, None)
    return tuple(seen)


def _referenced_parameters(revision: ModeloRevision) -> tuple[ParameterId, ...]:
    seen: dict[ParameterId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for parameter in expression_parameter_refs(formula.expression):
            seen.setdefault(parameter, None)
    return tuple(seen)


def _referenced_bindings(revision: ModeloRevision) -> tuple[BindingId, ...]:
    seen: dict[BindingId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for binding in expression_binding_refs(formula.expression):
            seen.setdefault(binding, None)
    return tuple(seen)


def _is_computed(casilla: CasillaDefinition) -> bool:
    return casilla.input_kind == InputKind.COMPUTED


def _select_active_brackets(
    definition: ParameterDefinition,
    *,
    on: date,
) -> tuple[BracketEntry, ...]:
    """Return the brackets temporally valid on `on`, sorted by lower_bound.

    Mirrors the runtime's `_resolve_bracket` filter so the rows the
    engine emits to `Tarifas` are exactly the rows the runtime would
    consult for the same base value on the same filing date.
    """
    active = tuple(
        entry
        for entry in definition.brackets
        if entry.valid_from <= on and (entry.valid_to is None or entry.valid_to >= on)
    )
    return tuple(sorted(active, key=lambda entry: entry.lower_bound))


def plan_layout(
    revision: ModeloRevision,
    *,
    bracket_filter_date: date | None = None,
    excluded_casilla_ids: frozenset[CasillaId] = frozenset(),
) -> SheetLayout:
    """Plan tab + row + column addresses for every casilla and parameter.

    Args:
        revision: The validated :class:`ModeloRevision` to lay out.
        bracket_filter_date: When supplied, bracket-table parameters
            are filtered to entries temporally valid on this date so
            the `Tarifas` rows the engine emits match the registry
            runtime's `_resolve_bracket` selection. When `None`, every
            bracket entry is emitted in `lower_bound` order.
        excluded_casilla_ids: Casillas to omit from the layout entirely.
            The engine uses this to drop ``internal_only`` computed
            casillas whose custom runtime-dispatch formula op has no
            closed-form Sheets translation (the M303 régimen-simplificado
            módulos advisory-support figures): they are absent from the
            AEAT official Diseño de Registros and cannot be rendered as a
            live spreadsheet formula, so they do not belong in the
            official-structure workbook.

    Returns:
        A :class:`SheetLayout` carrying cell addresses for every casilla,
        binding, parameter, and relation defined on the revision.
    """
    value_column = _ENTRADAS_VALUE_COLUMN
    anchor_column = _TARIFFS_ANCHOR_COLUMN

    casilla_plan = _layout_casillas(
        revision,
        value_column=value_column,
        excluded_casilla_ids=excluded_casilla_ids,
    )
    binding_plan = _layout_bindings(
        revision,
        value_column=value_column,
        entradas_row_start=casilla_plan.entradas_next_row,
    )
    parameter_plan = _layout_parameters(
        revision,
        anchor_column=anchor_column,
        tariffs_row_start=_TARIFFS_HEADER_OFFSET + 1,
        bracket_filter_date=bracket_filter_date,
    )
    relation_cells = _layout_relations(
        revision,
        anchor_column=anchor_column,
        tariffs_row_start=parameter_plan.tariffs_next_row,
    )
    return SheetLayout(
        revision_id=revision.id,
        entradas_cells=casilla_plan.entradas_cells,
        calculos_cells=casilla_plan.calculos_cells,
        binding_cells=binding_plan.binding_cells,
        date_binding_cells=binding_plan.date_binding_cells,
        filing_year=bracket_filter_date.year if bracket_filter_date is not None else 0,
        parameter_cells=parameter_plan.parameter_cells,
        relation_cells=relation_cells,
        entradas_rows=tuple(casilla_plan.entradas_rows),
        calculos_rows=tuple(casilla_plan.calculos_rows),
        binding_rows=tuple(binding_plan.binding_rows),
        tariff_anchors=parameter_plan.tariff_anchors,
        bracket_ranges=parameter_plan.bracket_ranges,
        bracket_entries=parameter_plan.bracket_entries,
    )


# Both data tabs share the same column layout:
# A=Section, B=Casilla number, C=Casilla label, D=Value.
_ENTRADAS_VALUE_COLUMN = 4
# Tariffs tab: column A holds the parameter id label, column C
# is the anchor cell (scalar value, or the bracket-table header).
_TARIFFS_ANCHOR_COLUMN = 3
# Row 1 of every tab is reserved for the header banner.
_DATA_HEADER_ROW = 1
_TARIFFS_HEADER_OFFSET = 1


@dataclass(frozen=True, slots=True)
class _CasillaPlan:
    """Bundle returned by _layout_casillas — casilla cells + row trackers."""

    entradas_cells: dict[CasillaId, SheetCellAddress]
    calculos_cells: dict[CasillaId, SheetCellAddress]
    entradas_rows: list[_CasillaRow]
    calculos_rows: list[_CasillaRow]
    entradas_next_row: int


def _layout_casillas(
    revision: ModeloRevision,
    *,
    value_column: int,
    excluded_casilla_ids: frozenset[CasillaId] = frozenset(),
) -> _CasillaPlan:
    """Assign each casilla a tab + row + value-cell address.

    Operator-input + informational casillas land on the Entradas
    tab in declaration order; computed casillas land on the
    Calculos tab. ``entradas_next_row`` is returned so the binding
    layout below appends rows below the casilla block on Entradas.

    ``excluded_casilla_ids`` casillas receive no cell or row (they are
    omitted from the workbook entirely — see :func:`plan_layout`).
    """
    entradas_cells: dict[CasillaId, SheetCellAddress] = {}
    calculos_cells: dict[CasillaId, SheetCellAddress] = {}
    entradas_rows: list[_CasillaRow] = []
    calculos_rows: list[_CasillaRow] = []
    entradas_row = _DATA_HEADER_ROW + 1
    calculos_row = _DATA_HEADER_ROW + 1
    for casilla in revision.casillas:
        if casilla.id in excluded_casilla_ids:
            continue
        if _is_computed(casilla):
            calculos_cells[casilla.id] = SheetCellAddress.at(TabName.CALCULOS, calculos_row, value_column)
            calculos_rows.append(
                _CasillaRow(
                    casilla_id=casilla.id,
                    tab=TabName.CALCULOS,
                    row=calculos_row,
                    section_path=casilla.section,
                ),
            )
            calculos_row += 1
            continue
        # Operator-input and informational casillas both occupy the
        # Entradas tab; informational rows are read-only at the
        # presentation layer but the layout coordinates are
        # identical.
        entradas_cells[casilla.id] = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
        entradas_rows.append(
            _CasillaRow(
                casilla_id=casilla.id,
                tab=TabName.ENTRADAS,
                row=entradas_row,
                section_path=casilla.section,
            ),
        )
        entradas_row += 1
    return _CasillaPlan(
        entradas_cells=entradas_cells,
        calculos_cells=calculos_cells,
        entradas_rows=entradas_rows,
        calculos_rows=calculos_rows,
        entradas_next_row=entradas_row,
    )


@dataclass(frozen=True, slots=True)
class _BindingPlan:
    """Bundle returned by _layout_bindings — caller-supplied numeric inputs on Entradas."""

    binding_cells: dict[BindingId, SheetCellAddress]
    binding_rows: list[_BindingRow]
    date_binding_cells: dict[BindingId, SheetCellAddress]


def _layout_bindings(
    revision: ModeloRevision,
    *,
    value_column: int,
    entradas_row_start: int,
) -> _BindingPlan:
    """Assign each referenced binding a row in the Entradas tab below the casilla block.

    Bindings carry caller-supplied numeric values (ledger
    aggregations, profile fields, previous-filing snapshots).
    Date bindings (e.g. taxpayer birth_date, consumed by the
    ``age_at_year_end`` op) take their own Entradas rows below the
    numeric bindings so the operator can enter the source date and the
    translator can compile ``YEAR(cell)``. Bindings referenced by
    formulas but not declared on the revision are silently skipped —
    registry validation already refused those.
    """
    binding_cells: dict[BindingId, SheetCellAddress] = {}
    binding_rows: list[_BindingRow] = []
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    entradas_row = entradas_row_start
    for binding_id in _referenced_bindings(revision):
        if binding_id not in bindings_by_id:
            raise _undeclared_layout_reference("binding")
        binding_cells[binding_id] = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
        binding_rows.append(_BindingRow(binding=binding_id, tab=TabName.ENTRADAS, row=entradas_row, label=binding_id))
        entradas_row += 1
    date_binding_cells: dict[BindingId, SheetCellAddress] = {}
    for binding_id in _referenced_date_bindings(revision):
        if binding_id in binding_cells:
            # Already laid out as a numeric binding; reuse its cell.
            date_binding_cells[binding_id] = binding_cells[binding_id]
            continue
        if binding_id not in bindings_by_id:
            raise _undeclared_layout_reference("date_binding")
        date_binding_cells[binding_id] = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
        binding_rows.append(_BindingRow(binding=binding_id, tab=TabName.ENTRADAS, row=entradas_row, label=binding_id))
        entradas_row += 1
    return _BindingPlan(binding_cells=binding_cells, binding_rows=binding_rows, date_binding_cells=date_binding_cells)


@dataclass(frozen=True, slots=True)
class _ParameterPlan:
    """Bundle returned by _layout_parameters — anchors + bracket tables on Tariffs."""

    parameter_cells: dict[ParameterId, ParameterCell]
    tariff_anchors: dict[ParameterId, SheetCellAddress]
    bracket_ranges: dict[ParameterId, BracketRanges]
    bracket_entries: dict[ParameterId, tuple[BracketEntry, ...]]
    tariffs_next_row: int


def _layout_parameters(
    revision: ModeloRevision,
    *,
    anchor_column: int,
    tariffs_row_start: int,
    bracket_filter_date: date | None,
) -> _ParameterPlan:
    """Assign each referenced parameter an anchor cell on the Tariffs tab.

    Scalar parameters take a single anchor cell; bracket-table
    parameters expand into a header row + N data rows
    (header: Cn=lower, Dn=upper, En=fixed, Fn=marginal). When
    ``bracket_filter_date`` is supplied, only entries temporally
    valid on that date are emitted so the registry runtime's
    ``_resolve_bracket`` selection matches what the sheet shows.
    """
    parameter_cells: dict[ParameterId, ParameterCell] = {}
    tariff_anchors: dict[ParameterId, SheetCellAddress] = {}
    bracket_ranges: dict[ParameterId, BracketRanges] = {}
    bracket_entries: dict[ParameterId, tuple[BracketEntry, ...]] = {}
    parameters_by_id: dict[ParameterId, ParameterDefinition] = {
        parameter.id: parameter for parameter in revision.parameters
    }
    tariffs_row = tariffs_row_start
    for parameter_id in _referenced_parameters(revision):
        if parameter_id not in parameters_by_id:
            raise _undeclared_layout_reference("parameter")
        definition = parameters_by_id[parameter_id]
        anchor = SheetCellAddress.at(TabName.TARIFFS, tariffs_row, anchor_column)
        tariff_anchors[parameter_id] = anchor
        parameter_cells[parameter_id] = ParameterCell(parameter=parameter_id, anchor=anchor)
        if definition.data_type != "bracket_table":
            tariffs_row += 2
            continue
        tariffs_row = _emit_bracket_table_layout(
            definition,
            parameter_id=parameter_id,
            anchor=anchor,
            anchor_column=anchor_column,
            bracket_filter_date=bracket_filter_date,
            bracket_ranges=bracket_ranges,
            bracket_entries=bracket_entries,
        )
    return _ParameterPlan(
        parameter_cells=parameter_cells,
        tariff_anchors=tariff_anchors,
        bracket_ranges=bracket_ranges,
        bracket_entries=bracket_entries,
        tariffs_next_row=tariffs_row,
    )


def _emit_bracket_table_layout(
    definition: ParameterDefinition,
    *,
    parameter_id: ParameterId,
    anchor: SheetCellAddress,
    anchor_column: int,
    bracket_filter_date: date | None,
    bracket_ranges: dict[ParameterId, BracketRanges],
    bracket_entries: dict[ParameterId, tuple[BracketEntry, ...]],
) -> int:
    """Emit one bracket-table layout block; return the next free tariffs row.

    Active entries are either temporally-filtered (when
    ``bracket_filter_date`` is supplied) or every declared bracket
    sorted by ``lower_bound``. ``row_count`` is at least 1 so an
    empty active set still reserves one header + one placeholder
    row — the layout never collapses to zero rows.
    """
    if bracket_filter_date is not None:
        active = _select_active_brackets(definition, on=bracket_filter_date)
    else:
        active = tuple(sorted(definition.brackets, key=lambda b: b.lower_bound))
    bracket_entries[parameter_id] = active
    row_count = max(len(active), 1)
    header_row = anchor.row
    first_data_row = header_row + 1
    last_data_row = header_row + row_count
    lower_col = column_index_to_letters(anchor_column)
    fa_col = column_index_to_letters(anchor_column + 2)
    mr_col = column_index_to_letters(anchor_column + 3)
    tab_name = TabName.TARIFFS.value
    bracket_ranges[parameter_id] = BracketRanges(
        parameter=parameter_id,
        lower_bound=(f"'{tab_name}'!{lower_col}{first_data_row}:{lower_col}{last_data_row}"),
        fixed_addition=(f"'{tab_name}'!{fa_col}{first_data_row}:{fa_col}{last_data_row}"),
        marginal_rate=(f"'{tab_name}'!{mr_col}{first_data_row}:{mr_col}{last_data_row}"),
        row_count=row_count,
    )
    return last_data_row + 2  # one blank row between regions


def _layout_relations(
    revision: ModeloRevision,
    *,
    anchor_column: int,
    tariffs_row_start: int,
) -> dict[RelationId, SheetCellAddress]:
    """Assign each referenced relation a single-value cell at the bottom of the Tariffs tab.

    Each cell holds a pre-resolved aggregation the caller supplies
    (e.g. annual roll-up of quarterly modelo 111 retentions feeding
    modelo 190). Relations referenced by formulas but undeclared on
    the revision are silently skipped — registry validation already
    refused those.
    """
    relation_cells: dict[RelationId, SheetCellAddress] = {}
    relations_by_id = {rel.id: rel for rel in revision.relations}
    tariffs_row = tariffs_row_start
    for relation_id in _referenced_relations(revision):
        if relation_id not in relations_by_id:
            raise _undeclared_layout_reference("relation")
        relation_cells[relation_id] = SheetCellAddress.at(TabName.TARIFFS, tariffs_row, anchor_column)
        tariffs_row += 2
    return relation_cells


__all__ = ["BracketRanges", "SheetLayout", "plan_layout"]
