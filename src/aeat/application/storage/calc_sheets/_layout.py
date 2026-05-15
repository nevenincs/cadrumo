"""Layout planner that maps every casilla, binding, and parameter of a
`ModeloRevision` onto a Sheets cell address.

The mapping is a pure function of the revision (and an optional
filing date for temporal bracket filtering). Two engine runs over
the same revision yield the same layout, and the pull adapter can
therefore round-trip a workbook back into casilla-id space without
consulting the source registry at runtime.

Layout strategy
---------------

- The `Entradas` tab lists every operator-input casilla (input_kind
  in {"manual", "bound", "informational"}). Each row carries
  `{section, casilla_number, label, value}` with the value cell
  anchored in column D. Bindings the formulas reference appear in
  their own rows below the casilla rows so the operator can review
  and override pre-resolved values.
- The `Cálculos` tab lists every computed casilla. Each row carries
  `{section, casilla_number, label, formula_value}` with the formula
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

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ....domain.calculations.registry._ids import BindingId, CasillaId, ParameterId, RelationId
from ....domain.calculations.registry._schema import (
    BracketEntry,
    CasillaDefinition,
    FormulaExpression,
    ModeloRevision,
    ParameterDefinition,
)
from ._records import (
    ParameterCell,
    SheetCellAddress,
    TabName,
    _column_index_to_letters,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _CasillaRow(BaseModel):
    model_config = _STRICT_FROZEN

    casilla: CasillaId
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
    """A1 ranges for the lower-bound, fixed-addition, and marginal-rate
    columns of one bracket-table parameter in the `Tarifas` tab.

    The translator's `lookup_bracket` handler resolves a bracket
    lookup against these ranges via:

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

    revision_id: str = Field(min_length=1)
    entradas_cells: Mapping[CasillaId, SheetCellAddress]
    calculos_cells: Mapping[CasillaId, SheetCellAddress]
    binding_cells: Mapping[BindingId, SheetCellAddress]
    parameter_cells: Mapping[ParameterId, ParameterCell]
    relation_cells: Mapping[RelationId, SheetCellAddress]
    entradas_rows: tuple[_CasillaRow, ...]
    calculos_rows: tuple[_CasillaRow, ...]
    binding_rows: tuple[_BindingRow, ...]
    tariff_anchors: Mapping[ParameterId, SheetCellAddress]
    bracket_ranges: Mapping[ParameterId, BracketRanges]
    bracket_entries: Mapping[ParameterId, tuple[BracketEntry, ...]]

    def address_for(self, casilla: CasillaId) -> SheetCellAddress:
        """Resolve a casilla reference to the cell holding its value.

        Computed casillas resolve to their `Cálculos` cell; input
        casillas resolve to their `Entradas` cell. The translator uses
        this to compile a `FormulaExpression` casilla leaf into an A1
        reference.
        """

        if casilla in self.calculos_cells:
            return self.calculos_cells[casilla]
        if casilla in self.entradas_cells:
            return self.entradas_cells[casilla]
        raise KeyError(f"unknown casilla in layout: {casilla!r}")

    def address_for_binding(self, binding: BindingId) -> SheetCellAddress:
        if binding not in self.binding_cells:
            raise KeyError(f"unknown binding in layout: {binding!r}")
        return self.binding_cells[binding]

    def address_for_relation(self, relation: RelationId) -> SheetCellAddress:
        if relation not in self.relation_cells:
            raise KeyError(f"unknown relation in layout: {relation!r}")
        return self.relation_cells[relation]


def _walk_expression_parameters(expression: FormulaExpression) -> Iterable[ParameterId]:
    if expression.parameter is not None:
        yield expression.parameter
    if expression.dispatch_table is not None:
        yield from expression.dispatch_table.values()
    for child in expression.args:
        yield from _walk_expression_parameters(child)


def _walk_expression_bindings(expression: FormulaExpression) -> Iterable[BindingId]:
    if expression.binding is not None:
        yield expression.binding
    for child in expression.args:
        yield from _walk_expression_bindings(child)


def _walk_expression_relations(expression: FormulaExpression) -> Iterable[RelationId]:
    if expression.relation is not None:
        yield expression.relation
    for child in expression.args:
        yield from _walk_expression_relations(child)


def _referenced_relations(revision: ModeloRevision) -> tuple[RelationId, ...]:
    seen: dict[RelationId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for relation in _walk_expression_relations(formula.expression):
            seen.setdefault(relation, None)
    return tuple(seen)


def _referenced_parameters(revision: ModeloRevision) -> tuple[ParameterId, ...]:
    seen: dict[ParameterId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for parameter in _walk_expression_parameters(formula.expression):
            seen.setdefault(parameter, None)
    return tuple(seen)


def _referenced_bindings(revision: ModeloRevision) -> tuple[BindingId, ...]:
    seen: dict[BindingId, None] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        for binding in _walk_expression_bindings(formula.expression):
            seen.setdefault(binding, None)
    return tuple(seen)


def _is_operator_input(casilla: CasillaDefinition) -> bool:
    return casilla.input_kind in ("manual", "bound")


def _is_computed(casilla: CasillaDefinition) -> bool:
    return casilla.input_kind == "computed"


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
) -> SheetLayout:
    """Plan tab + row + column addresses for every casilla and parameter.

    Args:
        revision: The validated revision to lay out.
        bracket_filter_date: When supplied, bracket-table parameters
            are filtered to entries temporally valid on this date so
            the `Tarifas` rows the engine emits match the registry
            runtime's `_resolve_bracket` selection. When `None`, every
            bracket entry is emitted in `lower_bound` order.
    """

    entradas_cells: dict[CasillaId, SheetCellAddress] = {}
    calculos_cells: dict[CasillaId, SheetCellAddress] = {}
    entradas_rows: list[_CasillaRow] = []
    calculos_rows: list[_CasillaRow] = []

    # Both data tabs share the same column layout:
    # A=Section, B=Casilla number, C=Casilla label, D=Value.
    value_column = 4

    entradas_row = 2  # Row 1 reserved for the header.
    calculos_row = 2

    for casilla in revision.casillas:
        if _is_operator_input(casilla):
            address = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
            entradas_cells[casilla.id] = address
            entradas_rows.append(
                _CasillaRow(
                    casilla=casilla.id,
                    tab=TabName.ENTRADAS,
                    row=entradas_row,
                    section_path=casilla.section,
                )
            )
            entradas_row += 1
        elif _is_computed(casilla):
            address = SheetCellAddress.at(TabName.CALCULOS, calculos_row, value_column)
            calculos_cells[casilla.id] = address
            calculos_rows.append(
                _CasillaRow(
                    casilla=casilla.id,
                    tab=TabName.CALCULOS,
                    row=calculos_row,
                    section_path=casilla.section,
                )
            )
            calculos_row += 1
        else:
            # Informational casillas appear in the Entradas tab as
            # read-only descriptive rows.
            address = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
            entradas_cells[casilla.id] = address
            entradas_rows.append(
                _CasillaRow(
                    casilla=casilla.id,
                    tab=TabName.ENTRADAS,
                    row=entradas_row,
                    section_path=casilla.section,
                )
            )
            entradas_row += 1

    # Bindings — caller-supplied numeric values (ledger aggregations,
    # profile fields, previous-filing snapshots) — occupy their own
    # rows in the Entradas tab below the casilla rows.
    binding_cells: dict[BindingId, SheetCellAddress] = {}
    binding_rows: list[_BindingRow] = []
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    for binding_id in _referenced_bindings(revision):
        definition = bindings_by_id.get(binding_id)
        if definition is None:
            continue
        address = SheetCellAddress.at(TabName.ENTRADAS, entradas_row, value_column)
        binding_cells[binding_id] = address
        binding_rows.append(
            _BindingRow(
                binding=binding_id,
                tab=TabName.ENTRADAS,
                row=entradas_row,
                label=binding_id,
            )
        )
        entradas_row += 1

    parameter_cells: dict[ParameterId, ParameterCell] = {}
    tariff_anchors: dict[ParameterId, SheetCellAddress] = {}
    bracket_ranges: dict[ParameterId, BracketRanges] = {}
    bracket_entries: dict[ParameterId, tuple[BracketEntry, ...]] = {}

    parameters_by_id: dict[ParameterId, ParameterDefinition] = {
        parameter.id: parameter for parameter in revision.parameters
    }

    # Tariffs tab: column A holds the parameter id label, column C
    # is the anchor cell (scalar value, or the bracket-table header).
    # Bracket tables occupy:
    #   header  : Cn=lower, Dn=upper, En=fixed, Fn=marginal
    #   row n+1 : first bracket entry
    #   ...
    tariffs_row = 2  # Row 1 reserved for the header banner.
    anchor_column = 3  # Column C.

    for parameter_id in _referenced_parameters(revision):
        if parameter_id not in parameters_by_id:
            continue
        definition = parameters_by_id[parameter_id]
        anchor = SheetCellAddress.at(TabName.TARIFFS, tariffs_row, anchor_column)
        tariff_anchors[parameter_id] = anchor
        parameter_cells[parameter_id] = ParameterCell(parameter=parameter_id, anchor=anchor)
        if definition.data_type == "bracket_table":
            if bracket_filter_date is not None:
                active = _select_active_brackets(definition, on=bracket_filter_date)
            else:
                active = tuple(sorted(definition.brackets, key=lambda b: b.lower_bound))
            bracket_entries[parameter_id] = active
            row_count = max(len(active), 1)
            header_row = anchor.row
            first_data_row = header_row + 1
            last_data_row = header_row + row_count
            lower_col = _column_index_to_letters(anchor_column)
            fa_col = _column_index_to_letters(anchor_column + 2)
            mr_col = _column_index_to_letters(anchor_column + 3)
            tab_name = TabName.TARIFFS.value
            bracket_ranges[parameter_id] = BracketRanges(
                parameter=parameter_id,
                lower_bound=(f"'{tab_name}'!{lower_col}{first_data_row}:{lower_col}{last_data_row}"),
                fixed_addition=(f"'{tab_name}'!{fa_col}{first_data_row}:{fa_col}{last_data_row}"),
                marginal_rate=(f"'{tab_name}'!{mr_col}{first_data_row}:{mr_col}{last_data_row}"),
                row_count=row_count,
            )
            tariffs_row = last_data_row + 2  # one blank row between regions
        else:
            tariffs_row += 2

    # Relations occupy single-value cells at the bottom of the
    # Tarifas tab. Each cell holds a pre-resolved aggregation the
    # caller supplies (e.g. annual roll-up of quarterly modelo 111
    # retentions feeding modelo 190). The translator resolves a
    # `relation` leaf to its allocated cell.
    relation_cells: dict[RelationId, SheetCellAddress] = {}
    relations_by_id = {rel.id: rel for rel in revision.relations}
    for relation_id in _referenced_relations(revision):
        if relation_id not in relations_by_id:
            # A relation referenced by a formula but undeclared on
            # the revision would already have failed registry
            # validation; defensive skip keeps the layout total.
            continue
        address = SheetCellAddress.at(TabName.TARIFFS, tariffs_row, anchor_column)
        relation_cells[relation_id] = address
        tariffs_row += 2

    return SheetLayout(
        revision_id=revision.id,
        entradas_cells=entradas_cells,
        calculos_cells=calculos_cells,
        binding_cells=binding_cells,
        parameter_cells=parameter_cells,
        relation_cells=relation_cells,
        entradas_rows=tuple(entradas_rows),
        calculos_rows=tuple(calculos_rows),
        binding_rows=tuple(binding_rows),
        tariff_anchors=tariff_anchors,
        bracket_ranges=bracket_ranges,
        bracket_entries=bracket_entries,
    )


__all__ = ["BracketRanges", "SheetLayout", "plan_layout"]
