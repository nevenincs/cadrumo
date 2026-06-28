"""Engine driver that compiles a :class:`RegistrySnapshot` into a ``SheetExportPlan``.

The engine walks every casilla, binding, and parameter declared in the
:class:`ModeloRevision` embedded in the snapshot and maps each to a
typed cell or range in the generated workbook plan.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Final, Literal

from ....core import Period
from ....core.i18n import tr
from ....domain.calculations.registry import (
    BindingAggregationOp,
    CasillaDefinition,
    CasillaId,
    DataBindingDefinition,
    FormulaDefinition,
    InputKind,
    ModeloRevision,
    ParameterDefinition,
    RegistrySnapshot,
    binding_aggregation_op,
    casillas_by_id,
)
from ._errors import CalcSheetsEngineError
from ._layout import SheetLayout, plan_layout
from ._records import (
    OperatorInputs,
    RelationValues,
    SheetAnchor,
    SheetCellAddress,
    SheetCellConstraint,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetProvenanceRow,
    SheetRowSet,
    SheetRowSetColumn,
    SheetSectionHeader,
    SheetTariffTable,
    SheetTariffTableRow,
    SheetValueCell,
    TabName,
    _utc_now,
)
from ._styling import compute_styling
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
    raise CalcSheetsEngineError(
        "unsupported registry rounding code",
        context={"formula_id": formula.id},
        translated_message="application.storage.calc_sheets.engine.errors.unsupported_rounding",
    )


def _wrap_rounded(expression: str, *, rule: str, scale: int | None) -> str:
    if rule == "none" or scale is None:
        return expression
    return f"ROUND({expression},{scale})"


def registry_sha(snapshot: RegistrySnapshot) -> str:
    """Stable identity hash of the calculation surface in this :class:`RegistrySnapshot`.

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
        tr(
            "application.storage.calc_sheets.engine.guide.period",
            modelo_title=modelo.title,
            period=snapshot.period,
            filing_year=snapshot.filing_year,
        ),
        tr("application.storage.calc_sheets.engine.guide.editable_cells"),
        tr("application.storage.calc_sheets.engine.guide.pull_command"),
    )


def _stamp_registry_metadata(snapshot: RegistrySnapshot) -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        engine_version=_ENGINE_VERSION,
        registry_sha=registry_sha(snapshot),
        exported_at=_utc_now(),
    )


def _value_cells_for_entradas(
    revision: ModeloRevision,
    layout: SheetLayout,
    inputs: OperatorInputs,
) -> tuple[SheetValueCell, ...]:
    by_id = casillas_by_id(revision)
    by_casilla_id = inputs.by_casilla_id()
    cells: list[SheetValueCell] = []
    # Header row.
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 1),
            value=tr("application.storage.calc_sheets.engine.labels.section"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 2),
            value=tr("application.storage.calc_sheets.engine.labels.casilla"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 3),
            value=tr("application.storage.calc_sheets.engine.labels.concept"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.ENTRADAS, 1, 4),
            value=tr("application.storage.calc_sheets.engine.labels.value"),
            role="label",
        ),
    )
    previous_section: tuple[str, ...] | None = None
    for row in layout.entradas_rows:
        casilla = by_id[row.casilla_id]
        # Show the section label once, on the row where the section changes
        # (rendered as a banner); intervening rows leave column A blank so the
        # tab reads like the official modelo rather than repeating the long
        # section id on every line.
        section = tuple(casilla.section)
        if section and section != previous_section:
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 1),
                    value=" › ".join(section),
                    role="label",
                ),
            )
            previous_section = section
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 2),
                value=casilla.number,
                role="label",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, row.row, 3),
                value=casilla.label,
                role="label",
            ),
        )
        seed = by_casilla_id.get(casilla.id)
        cells.append(
            SheetValueCell(
                address=layout.entradas_cells[casilla.id],
                value=seed.value if seed is not None else None,
                casilla_id=casilla.id,
                role="operator_input",
            ),
        )
    for binding_row in layout.binding_rows:
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 1),
                value=tr("application.storage.calc_sheets.engine.labels.source"),
                role="label",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 2),
                value="—",
                role="label",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, binding_row.row, 3),
                value=binding_row.label,
                role="label",
            ),
        )
        binding = binding_row.binding
        # Numeric bindings live in ``binding_cells``; date bindings (consumed by
        # the ``age_at_year_end`` op) live in ``date_binding_cells``. Both render
        # as an operator-input Entradas cell.
        binding_address = (
            layout.binding_cells[binding] if binding in layout.binding_cells else layout.date_binding_cells[binding]
        )
        cells.append(
            SheetValueCell(
                address=binding_address,
                value=None,
                role="operator_input",
            ),
        )
    return tuple(cells)


def _label_cells_for_calculos(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetValueCell, ...]:
    by_id = casillas_by_id(revision)
    cells: list[SheetValueCell] = []
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 1),
            value=tr("application.storage.calc_sheets.engine.labels.section"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 2),
            value=tr("application.storage.calc_sheets.engine.labels.casilla"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 3),
            value=tr("application.storage.calc_sheets.engine.labels.concept"),
            role="label",
        ),
    )
    cells.append(
        SheetValueCell(
            address=SheetCellAddress.at(TabName.CALCULOS, 1, 4),
            value=tr("application.storage.calc_sheets.engine.labels.value"),
            role="label",
        ),
    )
    previous_section: tuple[str, ...] | None = None
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla_id]
        section = tuple(casilla.section)
        if section and section != previous_section:
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(TabName.CALCULOS, row.row, 1),
                    value=" › ".join(section),
                    role="label",
                ),
            )
            previous_section = section
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, row.row, 2),
                value=casilla.number,
                role="label",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, row.row, 3),
                value=casilla.label,
                role="label",
            ),
        )
    return tuple(cells)


def _formula_cells(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetFormulaCell, ...]:
    by_id = casillas_by_id(revision)
    formulas = {formula.id: formula for formula in revision.formulas}
    cells: list[SheetFormulaCell] = []
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla_id]
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        body = translate_formula(formula.expression, layout=layout)
        rule, scale = _rounding_rule_for(formula)
        cells.append(
            SheetFormulaCell(
                address=layout.calculos_cells[casilla.id],
                formula=_wrap_rounded(body, rule=rule, scale=scale),
                casilla_id=casilla.id,
                rounding_scale=scale,
                rounding_rule=rule,
            ),
        )
    return tuple(cells)


def _resolve_scalar(parameter: ParameterDefinition, today: date) -> Decimal:
    """Pick the dated scalar value valid on `today`.

    The engine emits the value at the snapshot's filing-period anchor
    so the workbook shows the parameter as it was at the filing date.
    Bracket-table parameters do not pass through this helper.
    """
    if parameter.data_type == "bracket_table":
        raise CalcSheetsEngineError(
            "parameter has no scalar value",
            context={"parameter_id": parameter.id, "data_type": parameter.data_type},
            translated_message="application.storage.calc_sheets.engine.errors.parameter_not_scalar",
        )
    chosen: Decimal | None = None
    for dated in parameter.values:
        if dated.valid_from > today:
            continue
        if dated.valid_to is not None and dated.valid_to < today:
            continue
        chosen = dated.value
    if chosen is None:
        raise CalcSheetsEngineError(
            "parameter has no dated value valid for requested date",
            context={"parameter_id": parameter.id, "valid_on": today.isoformat()},
            translated_message="application.storage.calc_sheets.engine.errors.parameter_no_dated_value",
        )
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
                sorted(definition.brackets, key=lambda b: b.lower_bound),
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
                ),
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
                ),
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
            ),
        )
        if table.data_type == "bracket_table":
            # Anchor row holds column headers; subsequent rows hold
            # lower/upper/fixed/marginal columns.
            header_row = anchor.row
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column),
                    value=tr("application.storage.calc_sheets.engine.labels.minimum_base"),
                    role="label",
                ),
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 1),
                    value=tr("application.storage.calc_sheets.engine.labels.maximum_base"),
                    role="label",
                ),
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 2),
                    value=tr("application.storage.calc_sheets.engine.labels.fixed_quota"),
                    role="label",
                ),
            )
            cells.append(
                SheetValueCell(
                    address=SheetCellAddress.at(anchor.tab, header_row, anchor.column + 3),
                    value=tr("application.storage.calc_sheets.engine.labels.marginal_rate"),
                    role="label",
                ),
            )
            for offset, row in enumerate(table.bracket_rows, start=1):
                bracket_row = header_row + offset
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column),
                        value=row.lower_bound,
                        parameter=table.parameter,
                        role="parameter_value",
                    ),
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 1),
                        value=row.upper_bound,
                        parameter=table.parameter,
                        role="parameter_value",
                    ),
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 2),
                        value=row.fixed_addition,
                        parameter=table.parameter,
                        role="parameter_value",
                    ),
                )
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(anchor.tab, bracket_row, anchor.column + 3),
                        value=row.marginal_rate,
                        parameter=table.parameter,
                        role="parameter_value",
                    ),
                )
        else:
            cells.append(
                SheetValueCell(
                    address=anchor,
                    value=table.scalar_value,
                    parameter=table.parameter,
                    role="parameter_value",
                ),
            )
    return tuple(cells)


def _provenance_rows(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetProvenanceRow, ...]:
    by_id: Mapping[CasillaId, CasillaDefinition] = casillas_by_id(revision)
    formulas = {formula.id: formula for formula in revision.formulas}
    rows: list[SheetProvenanceRow] = []
    for row in layout.calculos_rows:
        casilla = by_id[row.casilla_id]
        if casilla.formula is None:
            continue
        formula = formulas[casilla.formula]
        rule, _ = _rounding_rule_for(formula)
        rows.append(
            SheetProvenanceRow(
                casilla_id=casilla.id,
                display_number=casilla.number,
                casilla_label=casilla.label,
                formula_id=formula.id,
                rounding_rule=rule,
                legal_refs=tuple(formula.legal_refs),
                source_refs=tuple(formula.source_refs),
                target_address=layout.calculos_cells[casilla.id],
            ),
        )
    return tuple(rows)


def _provenance_value_cells(rows: Iterable[SheetProvenanceRow]) -> tuple[SheetValueCell, ...]:
    cells: list[SheetValueCell] = [
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 1),
            value=tr("application.storage.calc_sheets.engine.labels.casilla"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 2),
            value=tr("application.storage.calc_sheets.engine.labels.number"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 3),
            value=tr("application.storage.calc_sheets.engine.labels.concept"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 4),
            value=tr("application.storage.calc_sheets.engine.labels.formula"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 5),
            value=tr("application.storage.calc_sheets.engine.labels.rounding"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 6),
            value=tr("application.storage.calc_sheets.engine.labels.legal_refs"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 7),
            value=tr("application.storage.calc_sheets.engine.labels.source_refs"),
            role="label",
        ),
        SheetValueCell(
            address=SheetCellAddress.at(TabName.PROVENANCE, 1, 8),
            value=tr("application.storage.calc_sheets.engine.labels.cell"),
            role="label",
        ),
    ]
    for index, row in enumerate(rows, start=2):
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 1),
                value=row.casilla_id,
                casilla_id=row.casilla_id,
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 2),
                value=row.display_number,
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 3),
                value=row.casilla_label,
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 4),
                value=row.formula_id or "",
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 5),
                value=row.rounding_rule,
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 6),
                value=", ".join(row.legal_refs),
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 7),
                value=", ".join(row.source_refs),
                role="metadata",
            ),
        )
        cells.append(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.PROVENANCE, index, 8),
                value=row.target_address.qualified(),
                role="metadata",
            ),
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
            ),
        )
        supplied = by_relation.get(relation_id)
        cells.append(
            SheetValueCell(
                address=anchor,
                value=supplied.value if supplied is not None else None,
                note=supplied.note if supplied is not None else None,
                role="parameter_value",
            ),
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
            description=tr("application.storage.calc_sheets.engine.protected.calculos"),
        ),
        SheetProtectedRange(
            tab=TabName.PROVENANCE,
            start_row=1,
            end_row=max(len(layout.calculos_rows) + 1, 1),
            start_column=1,
            end_column=8,
            description=tr("application.storage.calc_sheets.engine.protected.provenance"),
        ),
        SheetProtectedRange(
            tab=TabName.TARIFFS,
            start_row=1,
            end_row=1000,
            start_column=1,
            end_column=8,
            description=tr("application.storage.calc_sheets.engine.protected.tariffs"),
        ),
        SheetProtectedRange(
            tab=TabName.GUIDE,
            start_row=1,
            end_row=200,
            start_column=1,
            end_column=4,
            description=tr("application.storage.calc_sheets.engine.protected.guide"),
        ),
    )


def _number_format_pattern(data_type: str) -> tuple[Literal["money", "integer", "percentage"], str] | None:
    if data_type == "money":
        return ("money", "#,##0.00")
    if data_type == "integer":
        return ("integer", "0")
    if data_type == "ratio":
        return ("percentage", "0.00%")
    return None


def _number_formats(
    revision: ModeloRevision,
    layout: SheetLayout,
) -> tuple[SheetNumberFormat, ...]:
    formats: list[SheetNumberFormat] = []
    for casilla in revision.casillas:
        pattern = _number_format_pattern(casilla.data_type)
        if pattern is None:
            continue
        data_type, format_pattern = pattern
        if casilla.input_kind == InputKind.COMPUTED:
            address = layout.calculos_cells.get(casilla.id)
        else:
            address = layout.entradas_cells.get(casilla.id)
        if address is None:
            continue
        formats.append(
            SheetNumberFormat(
                address=address,
                casilla_id=casilla.id,
                data_type=data_type,
                pattern=format_pattern,
            ),
        )
    return tuple(formats)


def _section_headers(layout: SheetLayout) -> tuple[SheetSectionHeader, ...]:
    """Mark the first label cell of each casilla section for bold styling.

    Walks the Entradas + Cálculos rows; whenever the section path changes, the
    column-A cell of that first row becomes a section header (the label text is
    already written by the value-cell pass — the facet only drives the styling).
    """
    headers: list[SheetSectionHeader] = []
    for rows in (layout.entradas_rows, layout.calculos_rows):
        previous: tuple[str, ...] | None = None
        for row in rows:
            section = tuple(row.section_path)
            if section and section != previous:
                headers.append(
                    SheetSectionHeader(
                        address=SheetCellAddress.at(row.tab, row.row, 1),
                        text=" › ".join(section),
                    ),
                )
                previous = section
    return tuple(headers)


def _anchors(layout: SheetLayout) -> tuple[SheetAnchor, ...]:
    """Emit explicit start (Entradas opening) + final (resultado) anchors.

    The start anchor marks the first operator-input row; the final anchor marks
    the last computed row (the filing result). Both land in a spare column beyond
    the data grid so they orient the inputs→resultado flow without colliding.
    """
    anchors: list[SheetAnchor] = []
    if layout.entradas_rows:
        first = layout.entradas_rows[0]
        anchors.append(
            SheetAnchor(
                address=SheetCellAddress.at(first.tab, first.row, 6),
                kind="start",
                label=tr("application.storage.calc_sheets.engine.anchors.start"),
            ),
        )
    if layout.calculos_rows:
        last = layout.calculos_rows[-1]
        anchors.append(
            SheetAnchor(
                address=SheetCellAddress.at(last.tab, last.row, 6),
                kind="final",
                label=tr("application.storage.calc_sheets.engine.anchors.final"),
            ),
        )
    return tuple(anchors)


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
        snapshot: The validated :class:`RegistrySnapshot` to export.
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

    Returns:
        A complete :class:`SheetExportPlan` ready for the apply adapter
        to write to disk.
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
    number_formats = _number_formats(revision, layout)
    section_headers = _section_headers(layout)
    anchors = _anchors(layout)
    anchor_value_cells = tuple(
        SheetValueCell(address=anchor.address, value=anchor.label, role="label") for anchor in anchors
    )
    cell_constraints = _collect_cell_constraints(revision, layout)
    row_sets = collect_row_sets(revision)

    metadata = _stamp_registry_metadata(snapshot)
    guide_paragraphs = _guide_paragraphs(snapshot)
    guide = SheetGuideContent(
        title=tr(
            "application.storage.calc_sheets.engine.guide.title",
            modelo_title=snapshot.modelo.title,
            period=snapshot.period,
            filing_year=snapshot.filing_year,
        ),
        paragraphs=guide_paragraphs,
    )

    value_cells = (
        entradas + calculos_labels + tariff_values + relation_value_cells + provenance_values + anchor_value_cells
    )

    styled_ranges, column_widths, frozen_views, auto_filters = compute_styling(
        layout=layout,
        section_headers=section_headers,
        anchors=anchors,
        provenance=provenance,
        guide_paragraphs=len(guide_paragraphs),
    )

    return SheetExportPlan(
        metadata=metadata,
        value_cells=value_cells,
        formula_cells=formula_cells,
        tariffs=tariff_tables,
        provenance=provenance,
        protected_ranges=protected,
        number_formats=number_formats,
        section_headers=section_headers,
        anchors=anchors,
        cell_constraints=cell_constraints,
        relation_provenance=relations,
        row_sets=row_sets,
        styled_ranges=styled_ranges,
        column_widths=column_widths,
        frozen_views=frozen_views,
        auto_filters=auto_filters,
        guide=guide,
    )


def collect_row_sets(revision: ModeloRevision) -> tuple[SheetRowSet, ...]:
    """Collect row-producer bindings into per-grouping `SheetRowSet` blocks.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are scanned for row-producer declarations.

    Walks `revision.bindings` for invoice / counterpart bindings with
    ``aggregation = { op = "rows" }``, groups them by ``selector.grouping``
    (typically ``operator_clave`` or ``operator_clave_period``), and lays
    them out as stacked header+data blocks in the `Detalle` tab. Each
    grouping occupies a contiguous column block; groupings stack
    vertically with a one-row gap between blocks. The pull adapter
    reads row data from `first_data_row` downwards.

    Each element in the returned tuple is a :class:`SheetRowSet`.
    """
    cohorts: dict[str, list[DataBindingDefinition]] = {}
    cohort_legal: dict[str, set[str]] = {}
    cohort_source: dict[str, set[str]] = {}
    for binding in revision.bindings:
        if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
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
            ),
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
                    casilla_id=casilla.id,
                ),
            )
    return tuple(constraints)


__all__ = ["build_export_plan"]
