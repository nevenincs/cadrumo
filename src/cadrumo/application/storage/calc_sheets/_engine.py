"""Engine driver that compiles a :class:`RegistrySnapshot` into a :class:`SheetExportPlan`.

The engine walks every casilla, binding, and parameter declared in the
:class:`ModeloRevision` embedded in the snapshot and maps each to a
typed cell or range in the generated workbook plan.

The result is renderer-neutral: Google Sheets and offline XLSX renderers both
consume the same :class:`SheetExportPlan`. The engine stamps registry identity,
formula provenance, relation prefills, styling facets, and row-set layout; the
ledger-evidence facet is supplied separately when the caller has bundled
:class:`cadrumo.domain.modelos.ledger_filing_snapshot.LedgerFilingEvidence`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import Final, Literal

from ....core import Period
from ....core.casilla_id import CasillaId
from ....core.aggregation import BindingSourceKind
from ....core.aggregation import BindingAggregationOp
from ....core.hashing import sha256_hex
from ....core.i18n import tr
from ....domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ....domain.calculations.registry.binding_selector_utils import (
    BindingRowSetSelector,
    binding_row_set_selector,
)
from ....domain.calculations.registry.casilla_membership import casillas_by_id
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ....domain.calculations.registry.relations import (
    relation_requirement_index,
    relation_source_requirements,
)
from ....domain.calculations.registry.schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_rounding import RegistryRoundingCode
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.period import calculation_filing_date
from ._layout import SheetLayout, plan_layout
from ._records import (
    OperatorInputs,
    RelationValue,
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
from ._translator import is_translatable, translate_formula
from .errors import CalcSheetsEngineError

# This stamp binds a rendered workbook to the layout compiler as well as the
# registry snapshot. Increment it whenever a change can move an operator
# input, relation, or tariff coordinate.
CALC_SHEETS_ENGINE_VERSION: Final[str] = "calc-sheets/0.2.0"
_ACQUISITION_MIRROR_BINDING_SUFFIX: Final[str] = "-adquisicion"


def _rounding_rule_for(
    formula: FormulaDefinition,
) -> tuple[Literal["money", "integer", "integer-ceiling", "none"], int | None]:
    """Map a registry rounding code to (rule_name, scale).

    The workbook is the SECOND interpreter of the registry rounding
    vocabulary: :func:`domain.calculations.registry._formula_runtime_ops.apply_rounding`
    evaluates it on the calculate path, and this renderer emits the live
    spreadsheet equivalent. A code handled in one and not the other makes
    the pull path and the calculate path disagree on the same casilla, so
    every :class:`~domain.calculations.registry.RegistryRoundingCode`
    member must be answered here.
    """
    if formula.rounding is None:
        return ("none", None)
    if formula.rounding == RegistryRoundingCode.MONEY_2:
        return ("money", 2)
    if formula.rounding == RegistryRoundingCode.INTEGER:
        return ("integer", 0)
    if formula.rounding == RegistryRoundingCode.INTEGER_CEILING:
        return ("integer-ceiling", 0)
    raise CalcSheetsEngineError(
        context={"formula_id": formula.id},
        translated_message="application.storage.calc_sheets.engine.errors.unsupported_rounding",
    )


def _wrap_rounded(expression: str, *, rule: str, scale: int | None) -> str:
    if rule == "none" or scale is None:
        return expression
    if rule == "integer-ceiling":
        # Spreadsheet counterpart of decimal.ROUND_CEILING: CEILING(x, 1)
        # takes x to the next whole unit up and leaves an already-integral
        # x untouched, matching LIVA art. 104.Dos ("se redondeará en la
        # unidad superior"). ROUND(x, 0) would round the ratio to the
        # NEAREST unit and understate the deduction below the half.
        return f"CEILING({expression},1)"
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
    return sha256_hex(canonical.encode("utf-8"))[:16]


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
        engine_version=CALC_SHEETS_ENGINE_VERSION,
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


def _tariff_tables(
    revision: ModeloRevision,
    layout: SheetLayout,
    filing_date: date,
) -> tuple[SheetTariffTable, ...]:
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    tables: list[SheetTariffTable] = []
    for parameter_id, anchor in layout.tariff_anchors.items():
        definition = parameters[parameter_id]
        if definition.data_type == "bracket_table":
            # Use the layout's pre-filtered active-bracket selection so
            # the Tarifas rows the engine emits match the runtime's
            # bracket selection exactly. Falling back to every entry
            # only happens when no temporal filter was applied at
            # layout time.
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
            raw_dt = definition.data_type
            if raw_dt not in ("decimal", "money", "integer", "ratio"):
                # Non-scalar parameter types that reach the tariff-anchor loop
                # without being a ``bracket_table`` (e.g. ``keyed_bracket_table`` --
                # the Modelo 303 módulos-IVA coefficients keyed by epígrafe:módulo)
                # cannot be materialised as a single scalar tariff value. Skip them
                # BEFORE scalar resolution: ``_resolve_scalar`` looks for dated
                # scalar ``values`` a keyed_bracket_table does not carry, and would
                # otherwise crash the whole workbook export.
                continue
            try:
                scalar = resolve_parameter(definition, {"filing_period": filing_date})
            except RegistryValidationError as exc:
                raise CalcSheetsEngineError(
                    context={"parameter_id": definition.id, "valid_on": filing_date.isoformat()},
                    translated_message="application.storage.calc_sheets.engine.errors.parameter_no_dated_value",
                ) from exc
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


def _relation_values_with_registry_grounding(
    snapshot: RegistrySnapshot,
    layout: SheetLayout,
    relation_values: RelationValues,
) -> RelationValues:
    """Attach registry-owned source identity and grounding to relation scalar rows."""
    supplied_by_relation = relation_values.by_relation()
    relations_by_id = {relation.id: relation for relation in snapshot.revision.relations}
    requirements_by_relation = relation_requirement_index(
        relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
    )
    values: list[RelationValue] = []
    for relation_id in layout.relation_cells:
        relation = relations_by_id[relation_id]
        supplied = supplied_by_relation.get(relation_id)
        requirement = requirements_by_relation.get(relation_id)
        source_modelo = requirement.source_modelo if requirement is not None else relation.source_modelo
        source_filing_year = (
            requirement.filing_year
            if requirement is not None
            else supplied.source_filing_year
            if supplied is not None
            else None
        )
        source_periods = requirement.periods if requirement is not None else relation.source_periods
        source_casilla_ids = (
            requirement.source_casilla_ids if requirement is not None else (relation.source_casilla_id,)
        )
        legal_refs = requirement.legal_refs if requirement is not None else relation.legal_refs
        source_refs = requirement.source_refs if requirement is not None else relation.source_refs
        values.append(
            RelationValue(
                relation=relation_id,
                value=supplied.value if supplied is not None else None,
                provenance=supplied.provenance if supplied is not None else "operator_manual",
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                source_casilla_ids=source_casilla_ids,
                dependency_treatment=(
                    (requirement.dependency_treatment or "")
                    if requirement is not None
                    else supplied.dependency_treatment
                    if supplied is not None
                    else ""
                ),
                legal_refs=legal_refs,
                source_refs=source_refs,
                resolved_at=supplied.resolved_at if supplied is not None else None,
                note=supplied.note if supplied is not None else None,
            ),
        )
    return RelationValues(values=tuple(values))


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
        # Evidencia is generated fact basis, never an operator surface. It was
        # protected offline by a bespoke whole-sheet call that the plan never
        # mentioned, so the online transport had nothing to act on and left it
        # editable. Declaring it here is what makes the two agree: the plan is
        # the protection contract, and a transport that protects something the
        # plan does not name is as wrong as one that skips something it does.
        SheetProtectedRange(
            tab=TabName.EVIDENCIA,
            start_row=1,
            end_row=1000,
            start_column=1,
            end_column=16,
            description=tr("application.storage.calc_sheets.engine.protected.evidencia"),
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


def _untranslatable_internal_only_casillas(
    revision: ModeloRevision,
    *,
    bracket_filter_date: date,
) -> frozenset[CasillaId]:
    """Return the ``internal_only`` computed casillas that cannot be exported.

    An ``internal_only`` casilla is app-internal calculation-support that the
    AEAT-published Diseño de Registros omits (it carries no ``export_refs`` and
    never reaches a filed casilla — the ``modelo-export-mirrors-official-structure``
    rule binds the workbook to the *official* structure). When such a casilla's
    formula has no closed-form Sheets translation, it cannot be rendered as a
    live workbook formula and is omitted from the export layout entirely: it is
    neither an official casilla the workbook must mirror nor a translatable cell.

    A *translatable* ``internal_only`` casilla (e.g. the Modelo 200
    ``bin-aplicada-maxima`` ceiling, computed from ``min``/``max``/``percent``)
    stays in the workbook — the exclusion is scoped to the untranslatable custom
    ops, not to ``internal_only`` as a whole.

    The exclusion is computed to a fixpoint. Excluding a casilla removes its cell
    from the layout, so an ``internal_only`` casilla that references it can become
    untranslatable in turn once the dependency is gone -- it must then be excluded
    as well, or ``_formula_cells`` would fail translating a leaf reference to a cell
    the layout no longer carries. Each pass rebuilds the probe layout with the
    exclusions found so far and re-checks the remaining ``internal_only`` casillas
    until no new one is untranslatable.
    """
    formulas = {formula.id: formula for formula in revision.formulas}
    excluded: set[CasillaId] = set()
    while True:
        probe_layout = plan_layout(
            revision,
            bracket_filter_date=bracket_filter_date,
            excluded_casilla_ids=frozenset(excluded),
        )
        newly_excluded: set[CasillaId] = set()
        for casilla in revision.casillas:
            if not casilla.internal_only or casilla.formula is None or casilla.id in excluded:
                continue
            formula = formulas[casilla.formula]
            if not is_translatable(formula.expression, layout=probe_layout):
                newly_excluded.add(casilla.id)
        if not newly_excluded:
            return frozenset(excluded)
        excluded |= newly_excluded


def build_export_plan(
    snapshot: RegistrySnapshot,
    *,
    operator_inputs: OperatorInputs | None = None,
    relation_values: RelationValues | None = None,
    relation_resolver: RelationResolver | None = None,
) -> SheetExportPlan:
    """Walk a registry snapshot and produce a complete `SheetExportPlan`.

    The plan is a pure function of `snapshot`, `operator_inputs`, and
    the resolved relation values: workbook renderers write exactly what is in
    the plan, no more, no less. Two engine runs with the same inputs yield the
    same plan modulo the `exported_at`
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
            `cadrumo.application.calculations.resolve_relations_from_local_store`).
            When supplied AND `relation_values` is None, the engine
            invokes the resolver and stamps each resolved value's
            provenance onto the workbook so the pull adapter can
            detect stale prefills. Explicit `relation_values` take
            precedence over the resolver.

    Returns:
        A complete :class:`SheetExportPlan` ready for the Google apply adapter
        or offline workbook serializer.
    """
    inputs = operator_inputs if operator_inputs is not None else OperatorInputs()
    if relation_values is not None:
        supplied_relations = relation_values
    elif relation_resolver is not None:
        supplied_relations = relation_resolver(snapshot)
    else:
        supplied_relations = RelationValues()
    revision = snapshot.revision
    # Anchor every temporal lookup (scalar parameter, bracket-table
    # window selection) at the snapshot's filing date so the workbook
    # mirrors the same registry slice the local runtime would consult.
    filing_anchor = (
        calculation_filing_date(snapshot.filing_period)
        if snapshot.filing_period is not None
        else date(snapshot.filing_year, 12, 31)
    )
    excluded = _untranslatable_internal_only_casillas(revision, bracket_filter_date=filing_anchor)
    layout = plan_layout(
        revision,
        bracket_filter_date=filing_anchor,
        excluded_casilla_ids=excluded,
    )
    relations = _relation_values_with_registry_grounding(snapshot, layout, supplied_relations)

    entradas = _value_cells_for_entradas(revision, layout, inputs)
    calculos_labels = _label_cells_for_calculos(revision, layout)
    tariff_tables = _tariff_tables(revision, layout, filing_anchor)
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
    cohorts: dict[str, list[tuple[DataBindingDefinition, BindingRowSetSelector]]] = {}
    cohort_legal: dict[str, set[str]] = {}
    cohort_source: dict[str, set[str]] = {}
    public_row_bindings_by_id = _collectible_row_bindings_by_id(revision)
    for binding in revision.bindings:
        if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
            continue
        selector = binding_row_set_selector(binding)
        if selector is None:
            continue
        if _is_public_row_mirror(binding, selector, public_row_bindings_by_id):
            continue
        cohorts.setdefault(selector.grouping, []).append((binding, selector))
        cohort_legal.setdefault(selector.grouping, set()).update(str(ref) for ref in binding.legal_refs)
        cohort_source.setdefault(selector.grouping, set()).update(str(ref) for ref in binding.source_refs)

    row_sets: list[SheetRowSet] = []
    next_row = 1
    for grouping in sorted(cohorts):
        members = sorted(cohorts[grouping], key=lambda item: item[0].id)
        header_row = next_row
        first_data_row = next_row + 1
        columns = tuple(
            SheetRowSetColumn(
                binding=binding.id,
                header_address=SheetCellAddress.at(TabName.DETALLE, header_row, column_index),
                header_label=_row_set_column_label(binding, selector),
                legal_refs=tuple(sorted(str(ref) for ref in binding.legal_refs)),
            )
            for column_index, (binding, selector) in enumerate(members, start=1)
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


def _collectible_row_bindings_by_id(revision: ModeloRevision) -> dict[str, DataBindingDefinition]:
    return {
        str(binding.id): binding
        for binding in revision.bindings
        if binding.source == BindingSourceKind.COLLECTIBLE_INVOICE
        and binding_aggregation_op(binding) == BindingAggregationOp.ROWS
    }


def _is_public_row_mirror(
    binding: DataBindingDefinition,
    selector: BindingRowSetSelector,
    public_row_bindings_by_id: Mapping[str, DataBindingDefinition],
) -> bool:
    if binding.source != BindingSourceKind.PAYABLE_INVOICE:
        return False
    binding_id = str(binding.id)
    if not binding_id.endswith(_ACQUISITION_MIRROR_BINDING_SUFFIX):
        return False
    public_binding_id = binding_id.removesuffix(_ACQUISITION_MIRROR_BINDING_SUFFIX)
    public_binding = public_row_bindings_by_id.get(public_binding_id)
    if public_binding is None:
        return False
    public_selector = binding_row_set_selector(public_binding)
    if public_selector is None:
        return False
    return selector.grouping == public_selector.grouping and selector.row_field == public_selector.row_field


def _row_set_column_label(binding: DataBindingDefinition, selector: BindingRowSetSelector) -> str:
    """Derive a human-readable column header for a row-set binding.

    Resolves the operator-facing label through the i18n translation
    catalogue keyed by ``selector.row_field``. Locale strings live
    under ``sheets.detalle.headers.*``; missing keys fall back to the
    binding id so the workbook still renders rather than 500-erroring.
    """
    return tr(f"sheets.detalle.headers.{selector.row_field}", default=binding.id)


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
