"""Engine driver that compiles a `RegistrySnapshot` into a `SheetExportPlan`."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Final, Literal

from ....core.i18n import tr
from ....domain.calculations.registry._schema import (
    CasillaDefinition,
    DataBindingDefinition,
    FormulaDefinition,
    InputKind,
    ModeloRevision,
    ParameterDefinition,
    RegistrySnapshot,
)
from ._layout import SheetLayout, plan_layout
from ._records import (
    OperatorInputs,
    RelationValues,
    SheetCellAddress,
    SheetCellConstraint,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetProtectedRange,
    SheetProvenanceRow,
    SheetRowSet,
    SheetRowSetColumn,
    SheetTariffTable,
    SheetTariffTableRow,
    SheetValueCell,
    TabName,
    _utc_now,
)
from ._translator import translate_formula

_ENGINE_VERSION: Final[str] = "calc-sheets/0.1.0"


def _rounding_rule_for(
    formula: FormulaDefinition,
) -> tuple[Literal["money", "integer", "none"], int | None]:
    """Map a registry rounding code to (rule_name, scale)."""

    if formula.rounding is None:
        return ("none", None)
    if formula.rounding == "money-2":
        return ("money", 2)
    if formula.rounding == "integer":
        return ("integer", 0)
    raise ValueError(f"unsupported registry rounding code {formula.rounding!r}")


def _wrap_rounded(expression: str, *, rule: str, scale: int | None) -> str:
    if rule == "none" or scale is None:
        return expression
    return f"ROUND({expression},{scale})"


def _registry_sha(snapshot: RegistrySnapshot) -> str:
    """Stable identity hash of the calculation surface in this snapshot.

    The hash covers casilla ids, formula expressions, and parameter
    values. Two snapshots that produce the same calculation graph
    yield the same SHA; any registry edit yields a different SHA.
    The pull adapter uses this to refuse merges that would silently
    cross a registry boundary.
    """

    canonical = snapshot.model_dump_json(exclude_none=False, by_alias=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _guide_paragraphs(snapshot: RegistrySnapshot) -> tuple[str, ...]:
    modelo = snapshot.modelo
    return (
        f"{modelo.title} — período {snapshot.period} / {snapshot.filing_year}.",
        "Edite únicamente las celdas de la pestaña 'Entradas'. El resto de pestañas "
        "están protegidas: 'Cálculos' contiene las casillas derivadas con fórmulas, "
        "'Procedencia' audita cada casilla calculada y 'Tarifas' refleja los "
        "parámetros vigentes consultados por las fórmulas.",
        "Para recoger sus ediciones en la base local, ejecute 'aeat config google sync calc pull' desde la CLI.",
    )


def _stamp_registry_metadata(snapshot: RegistrySnapshot) -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        engine_version=_ENGINE_VERSION,
        registry_sha=_registry_sha(snapshot),
        exported_at=_utc_now(),
    )


def _value_cells_for_entradas(
    revision: ModeloRevision,
    layout: SheetLayout,
    inputs: OperatorInputs,
) -> tuple[SheetValueCell, ...]:
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    by_casilla = inputs.by_casilla()
    cells: list[SheetValueCell] = []
    # Header row.
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 1),
            value="Sección",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 2),
            value="Casilla",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 3),
            value="Concepto",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 4),
            value="Valor",
            role="label",
        )
    )
    for row in layout.entradas_rows:
        casilla = by_id[row.casilla]
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 1),
                value=" › ".join(casilla.section),
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 2),
                value=casilla.number,
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 3),
                value=casilla.label,
                role="label",
            )
        )
        seed = by_casilla.get(casilla.id)
        cells.append(
            SheetValueCell(
                address=layout.entradas_cells[casilla.id],
                value=seed.value if seed is not None else None,
                casilla=casilla.id,
                role="operator_input",
            )
        )
    for binding_row in layout.binding_rows:
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 1),
                value="Origen",
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 2),
                value="—",
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 3),
                value=binding_row.label,
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=layout.binding_cells[binding_row.binding],
                value=None,
                role="operator_input",
            )
        )
    return tuple(cells)


def _label_cells_for_calculos(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetValueCell, ...]:
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    cells: list[SheetValueCell] = []
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 1),
            value="Sección",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 2),
            value="Casilla",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 3),
            value="Concepto",
            role="label",
        )
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 4),
            value="Valor",
            role="label",
        )
    )
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla]
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, row.row, 1),
                value=" › ".join(casilla.section),
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, row.row, 2),
                value=casilla.number,
                role="label",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, row.row, 3),
                value=casilla.label,
                role="label",
            )
        )
    return tuple(cells)


def _formula_cells(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetFormulaCell, ...]:
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}
    cells: list[SheetFormulaCell] = []
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla]
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        body = translate_formula(formula.expression, layout=layout)
        rule, scale = _rounding_rule_for(formula)
        cells.append(
            SheetFormulaCell(
                address=layout.calculos_cells[casilla.id],
                formula=_wrap_rounded(body, rule=rule, scale=scale),
                casilla=casilla.id,
                rounding_scale=scale,
                rounding_rule=rule,
            )
        )
    return tuple(cells)


def _resolve_scalar(parameter: ParameterDefinition, today: date) -> Decimal:
    """Pick the dated scalar value valid on `today`.

    The engine emits the value at the snapshot's filing-period anchor
    so the workbook shows the parameter as it was at the filing date.
    Bracket-table parameters do not pass through this helper.
    """

    if parameter.data_type == "bracket_table":
        raise ValueError(f"bracket_table parameter {parameter.id!r} has no scalar value")
    chosen: Decimal | None = None
    for dated in parameter.values:
        if dated.valid_from > today:
            continue
        if dated.valid_to is not None and dated.valid_to < today:
            continue
        chosen = dated.value
    if chosen is None:
        raise ValueError(f"parameter {parameter.id!r} has no dated value valid for {today.isoformat()}")
    return chosen


def _tariff_tables(
    revision: ModeloRevision,
    layout: SheetLayout,
    filing_year: int,
) -> tuple[SheetTariffTable, ...]:
    today = date(filing_year, 12, 31)
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    tables: list[SheetTariffTable] = []
    for parameter_id, anchor in layout.tariff_anchors.items():
        definition = parameters[parameter_id]
        if definition.data_type == "bracket_table":
            # Use the layout's pre-filtered active-bracket selection so
            # the Tarifas rows the engine emits match the runtime's
            # bracket selection exactly. Falling back to every entry
            # only happens when no temporal filter was applied at
            # layout time (legacy callers).
            active = layout.bracket_entries.get(parameter_id) or tuple(
                sorted(definition.brackets, key=lambda b: b.lower_bound)
            )
            rows = tuple(
                SheetTariffTableRow(
                    lower_bound=bracket.lower_bound,
                    upper_bound=bracket.upper_bound,
                    fixed_addition=bracket.fixed_addition,
                    marginal_rate=bracket.marginal_rate,
                    valid_from=bracket.valid_from,
                    valid_to=bracket.valid_to,
                )
                for bracket in active
            )
            tables.append(
                SheetTariffTable(
                    parameter=parameter_id,
                    label=parameter_id,
                    data_type="bracket_table",
                    anchor=anchor,
                    bracket_rows=rows,
                )
            )
        else:
            scalar = _resolve_scalar(definition, today)
            raw_dt = definition.data_type
            if raw_dt not in ("decimal", "money", "integer", "ratio"):
                continue
            scalar_data_type: Literal["decimal", "money", "integer", "ratio"] = raw_dt
            tables.append(
                SheetTariffTable(
                    parameter=parameter_id,
                    label=parameter_id,
                    data_type=scalar_data_type,
                    anchor=anchor,
                    scalar_value=scalar,
                )
            )
    return tuple(tables)


def _tariff_value_cells(
    tariffs: Iterable[SheetTariffTable],
) -> tuple[SheetValueCell, ...]:
    """Materialise tariff tables as actual cell values in the workbook.

    Scalar tariffs occupy one labelled cell at the parameter's anchor;
    bracket tables occupy the anchor + a header row + N bracket rows.
    """

    cells: list[SheetValueCell] = []
    for table in tariffs:
        anchor = table.anchor
        label_address = SheetCellAddress.at(anchor.tab, anchor.row, anchor.column - 2)
        cells.append(
            SheetValueCell(
                address=label_address,
                value=table.label,
                parameter=table.parameter,
                role="label",
            )
        )
        if table.data_type == "bracket_table":
            # Anchor row holds column headers; subsequent rows hold
            # lower/upper/fixed/marginal columns.
            header_row = anchor.row
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column),
                    value="Base mínima",
                    role="label",
                )
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 1),
                    value="Base máxima",
                    role="label",
                )
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 2),
                    value="Cuota fija",
                    role="label",
                )
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 3),
                    value="Tipo marginal",
                    role="label",
                )
            )
            for offset, row in enumerate(table.bracket_rows, start=1):
                bracket_row = header_row + offset
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column),
                        value=row.lower_bound,
                        parameter=table.parameter,
                        role="parameter_value",
                    )
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 1),
                        value=row.upper_bound,
                        parameter=table.parameter,
                        role="parameter_value",
                    )
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 2),
                        value=row.fixed_addition,
                        parameter=table.parameter,
                        role="parameter_value",
                    )
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 3),
                        value=row.marginal_rate,
                        parameter=table.parameter,
                        role="parameter_value",
                    )
                )
        else:
            cells.append(
                SheetValueCell(
                    address=anchor,
                    value=table.scalar_value,
                    parameter=table.parameter,
                    role="parameter_value",
                )
            )
    return tuple(cells)


def _provenance_rows(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetProvenanceRow, ...]:
    by_id: Mapping[str, CasillaDefinition] = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}
    rows: list[SheetProvenanceRow] = []
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla]
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        rule, _ = _rounding_rule_for(formula)
        rows.append(
            SheetProvenanceRow(
                casilla_id=casilla.id,
                casilla_number=casilla.number,
                casilla_label=casilla.label,
                formula_id=formula.id,
                rounding_rule=rule,
                legal_refs=tuple(formula.legal_refs),
                source_refs=tuple(formula.source_refs),
                target_address=layout.calculos_cells[casilla.id],
            )
        )
    return tuple(rows)


def _provenance_value_cells(rows: Iterable[SheetProvenanceRow]) -> tuple[SheetValueCell, ...]:
    cells: list[SheetValueCell] = [
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 1),
            value="Casilla",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 2),
            value="Nº",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 3),
            value="Concepto",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 4),
            value="Fórmula",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 5),
            value="Redondeo",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 6),
            value="Ref. legales",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 7),
            value="Ref. fuentes",
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 8),
            value="Celda",
            role="label",
        ),
    ]
    for index, row in enumerate(rows, start=2):
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 1),
                value=row.casilla_id,
                casilla=row.casilla_id,
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 2),
                value=row.casilla_number,
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 3),
                value=row.casilla_label,
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 4),
                value=row.formula_id or "",
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 5),
                value=row.rounding_rule,
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 6),
                value=", ".join(row.legal_refs),
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 7),
                value=", ".join(row.source_refs),
                role="metadata",
            )
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 8),
                value=row.target_address.qualified(),
                role="metadata",
            )
        )
    return tuple(cells)


def _relation_value_cells(
    layout: SheetLayout,
    relation_values: RelationValues,
) -> tuple[SheetValueCell, ...]:
    """Mirror caller-supplied cross-revision aggregations to `Tarifas` cells.

    The engine reserves one cell per relation referenced by the
    revision's formulas (see the layout planner's `relation_cells`
    mapping). For each reserved cell we emit:

    - a label cell at `column - 2` carrying the relation id, so the
      operator reading the workbook can identify the aggregation
      without consulting the registry, and
    - the value cell itself at the relation's anchor, populated with
      the caller's pre-resolved scalar when available; a blank cell
      is emitted otherwise so the Sheets formula reads 0 (operators
      who export without supplying relations get a valid workbook
      with a clearly-blank cell to fill in by hand).
    """

    by_relation = relation_values.by_relation()
    cells: list[SheetValueCell] = []
    for relation_id, anchor in layout.relation_cells.items():
        label_address = SheetCellAddress.at(anchor.tab, anchor.row, anchor.column - 2)
        cells.append(
            SheetValueCell(
                address=label_address,
                value=relation_id,
                role="label",
            )
        )
        supplied = by_relation.get(relation_id)
        cells.append(
            SheetValueCell(
                address=anchor,
                value=supplied.value if supplied is not None else None,
                note=supplied.note if supplied is not None else None,
                role="parameter_value",
            )
        )
    return tuple(cells)


def _protected_ranges(layout: SheetLayout) -> tuple[SheetProtectedRange, ...]:
    last_calc_row = max((row.row for row in layout.calculos_rows), default=1)
    return (
        SheetProtectedRange(
            tab=TabName.CALCULOS,
            start_row=1,
            end_row=max(last_calc_row, 1),
            start_column=1,
            end_column=4,
            description="Cálculos derivados — protegido para preservar paridad",
        ),
        SheetProtectedRange(
            tab=TabName.PROVENANCE,
            start_row=1,
            end_row=max(len(layout.calculos_rows) + 1, 1),
            start_column=1,
            end_column=8,
            description="Procedencia / audit trail — protegido",
        ),
        SheetProtectedRange(
            tab=TabName.TARIFFS,
            start_row=1,
            end_row=1000,
            start_column=1,
            end_column=8,
            description="Tarifas / parámetros vigentes — protegido",
        ),
        SheetProtectedRange(
            tab=TabName.GUIDE,
            start_row=1,
            end_row=200,
            start_column=1,
            end_column=4,
            description="Guía — protegido",
        ),
    )


RelationResolver = Callable[[RegistrySnapshot], RelationValues]


def build_export_plan(
    snapshot: RegistrySnapshot,
    *,
    operator_inputs: OperatorInputs | None = None,
    relation_values: RelationValues | None = None,
    relation_resolver: RelationResolver | None = None,
) -> SheetExportPlan:
    """Walk a registry snapshot and produce a complete `SheetExportPlan`.

    The plan is a pure function of `snapshot`, `operator_inputs`, and
    the resolved relation values: the apply adapter writes exactly
    what is in the plan, no more, no less. Two engine runs with the
    same inputs yield the same plan modulo the `exported_at`
    timestamp.

    Args:
        snapshot: The validated registry snapshot to export.
        operator_inputs: Optional pre-populated operator-input values
            for the `Entradas` tab. Casillas not supplied here render
            as blank cells the operator fills in by hand.
        relation_values: Optional pre-resolved cross-revision
            aggregations mirrored into the `Tarifas` tab. Required
            when the revision's formulas consume `relation` leaves
            (annual roll-ups like modelo 190 over modelo 111); when
            absent and `relation_resolver` is also unset, the engine
            emits blank cells the operator must populate before the
            Sheet's formulas yield correct values.
        relation_resolver: Optional callable that resolves the
            snapshot's relations from a structured source (typically
            the local observation store via
            `aeat.application.calculations.resolve_relations_from_local_store`).
            When supplied AND `relation_values` is None, the engine
            invokes the resolver and stamps each resolved value's
            provenance onto the workbook so the pull adapter can
            detect stale prefills. Explicit `relation_values` take
            precedence over the resolver.
    """

    inputs = operator_inputs if operator_inputs is not None else OperatorInputs()
    if relation_values is not None:
        relations = relation_values
    elif relation_resolver is not None:
        relations = relation_resolver(snapshot)
    else:
        relations = RelationValues()
    revision = snapshot.revision
    # Anchor every temporal lookup (scalar parameter, bracket-table
    # window selection) at the snapshot's filing date so the workbook
    # mirrors the same registry slice the local runtime would consult.
    filing_anchor = date(snapshot.filing_year, 12, 31)
    layout = plan_layout(revision, bracket_filter_date=filing_anchor)

    entradas = _value_cells_for_entradas(revision, layout, inputs)
    calculos_labels = _label_cells_for_calculos(revision, layout)
    tariff_tables = _tariff_tables(revision, layout, snapshot.filing_year)
    tariff_values = _tariff_value_cells(tariff_tables)
    relation_value_cells = _relation_value_cells(layout, relations)
    formula_cells = _formula_cells(revision, layout)
    provenance = _provenance_rows(revision, layout)
    provenance_values = _provenance_value_cells(provenance)
    protected = _protected_ranges(layout)
    cell_constraints = _collect_cell_constraints(revision, layout)
    row_sets = collect_row_sets(revision)

    metadata = _stamp_registry_metadata(snapshot)
    guide = SheetGuideContent(
        title=f"{snapshot.modelo.title} — {snapshot.period}/{snapshot.filing_year}",
        paragraphs=_guide_paragraphs(snapshot),
    )

    value_cells = entradas + calculos_labels + tariff_values + relation_value_cells + provenance_values

    return SheetExportPlan(
        metadata=metadata,
        value_cells=value_cells,
        formula_cells=formula_cells,
        tariffs=tariff_tables,
        provenance=provenance,
        protected_ranges=protected,
        cell_constraints=cell_constraints,
        relation_provenance=relations,
        row_sets=row_sets,
        guide=guide,
    )


def collect_row_sets(revision: ModeloRevision) -> tuple[SheetRowSet, ...]:
    """Collect row-producer bindings into per-grouping `SheetRowSet` blocks.

    Walks `revision.bindings` for invoice / counterpart bindings with
    ``aggregation = { op = "rows" }``, groups them by ``selector.grouping``
    (typically ``operator_clave`` or ``operator_clave_period``), and lays
    them out as stacked header+data blocks in the `Detalle` tab. Each
    grouping occupies a contiguous column block; groupings stack
    vertically with a one-row gap between blocks. The pull adapter
    reads row data from `first_data_row` downwards.
    """

    cohorts: dict[str, list[DataBindingDefinition]] = {}
    cohort_legal: dict[str, set[str]] = {}
    cohort_source: dict[str, set[str]] = {}
    for binding in revision.bindings:
        aggregation = binding.aggregation or {}
        if str(aggregation.get("op")) != "rows":
            continue
        # `binding.selector` is a Mapping; getattr returns the default
        # for every Mapping regardless of key, so the lookup must go
        # through `.get`. The previous getattr-form silently dropped
        # every row-producer binding (entire Detalle tab empty).
        grouping = str(binding.selector.get("grouping", "") or "")
        if not grouping:
            continue
        cohorts.setdefault(grouping, []).append(binding)
        cohort_legal.setdefault(grouping, set()).update(str(ref) for ref in binding.legal_refs)
        cohort_source.setdefault(grouping, set()).update(str(ref) for ref in binding.source_refs)

    row_sets: list[SheetRowSet] = []
    next_row = 1
    for grouping in sorted(cohorts):
        members = sorted(cohorts[grouping], key=lambda b: b.id)
        header_row = next_row
        first_data_row = next_row + 1
        columns = tuple(
            SheetRowSetColumn(
                binding=binding.id,
                header_address=SheetCellAddress.at(TabName.DETALLE, header_row, column_index),
                header_label=_row_set_column_label(binding),
                legal_refs=tuple(sorted(str(ref) for ref in binding.legal_refs)),
            )
            for column_index, binding in enumerate(members, start=1)
        )
        row_sets.append(
            SheetRowSet(
                grouping=grouping,
                tab=TabName.DETALLE,
                header_row=header_row,
                first_data_row=first_data_row,
                columns=columns,
                legal_refs=tuple(sorted(cohort_legal[grouping])),
                source_refs=tuple(sorted(cohort_source[grouping])),
            )
        )
        # Reserve 50 data rows per grouping + one blank separator. The
        # apply adapter does not protect this area; operators may extend
        # downwards if more rows are needed.
        next_row = first_data_row + 50 + 1
    return tuple(row_sets)


def _row_set_column_label(binding: DataBindingDefinition) -> str:
    """Derive a human-readable column header for a row-set binding.

    Resolves the operator-facing label through the i18n translation
    catalogue keyed by ``selector.row_field``. Locale strings live
    under ``sheets.detalle.headers.*``; missing keys fall back to the
    binding id so the workbook still renders rather than 500-erroring.
    """

    # `binding.selector` is a Mapping; getattr returns the default for
    # every Mapping regardless of key, so the row_field lookup must go
    # through `.get`. The previous getattr-form silently dropped every
    # row_field name and surfaced the binding id as the operator-facing
    # column header (regression caught by test_detail_record_modelo_coverage).
    row_field = binding.selector.get("row_field")
    if isinstance(row_field, str) and row_field:
        return tr(f"sheets.detalle.headers.{row_field}", default=binding.id)
    return binding.id


def _collect_cell_constraints(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetCellConstraint, ...]:
    """Mirror each casilla's declared `constraints` onto its target cell.

    Computed casillas resolve their cell address through the
    `Cálculos` map; manual / bound casillas resolve through the
    `Entradas` map. Informational casillas are skipped.
    """

    constraints: list[SheetCellConstraint] = []
    for casilla in revision.casillas:
        if casilla.constraints is None:
            continue
        if casilla.input_kind == InputKind.COMPUTED:
            address = layout.calculos_cells.get(casilla.id)
        elif casilla.input_kind in (InputKind.MANUAL, InputKind.BOUND):
            address = layout.entradas_cells.get(casilla.id)
        else:
            continue
        if address is None:
            continue
        constraints.append(
            SheetCellConstraint(
                address=address,
                sign=casilla.constraints.sign,
                min_value=casilla.constraints.min_value,
                max_value=casilla.constraints.max_value,
                legal_refs=tuple(casilla.constraints.legal_refs),
                casilla=casilla.id,
            )
        )
    return tuple(constraints)


__all__ = ["build_export_plan"]
