"""Project declared registry forms onto the shared, transport-neutral workbook.

The form is a read-only presentation of existing calculation cells. It never
reconstructs fiscal formulas, invents data, or infers official page structure.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from textwrap import wrap

from ....core.i18n.render import lookup_translation, tr
from ....core.period import AD_HOC_PERIOD_CODE, Period
from ....domain.calculations.registry.export_semantics import ExportDraftAttribute
from ....domain.calculations.registry.form_context import form_context_choice, resolve_form_context_field
from ....domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormPageCondition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
)
from ....domain.calculations.registry.schema_verification import (
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)
from ....domain.modelos.calculation_revision import CalculationRevision
from ...export.review_form_data import ReviewSavedForm
from ...filing.export_producer import filing_producer_values
from ...filing.producer_snapshot import FilingProducerSnapshot
from ...modelo.settlement_casilla import declaration_result_casillas
from ...modelo.value_presentation import VALUE_FALSE_LOCALE_KEY, VALUE_TRUE_LOCALE_KEY
from ...modelo.work_form_context_values import form_context_value
from ...modelo.work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from ...modelo.work_form_records import saved_form_records
from .engine import registry_sha
from .errors import CalcSheetsEngineError
from .form_value_presentation import compact_date_casillas, compact_date_expression
from .human_workbook import human_template_preview, human_workbook
from .number_formats import numeric_format
from .records import (
    SheetAdministrativeFrame,
    SheetCellAddress,
    SheetColumnWidth,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetFrozenView,
    SheetMergedRange,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetRoundingRule,
    SheetRowHeight,
    SheetStyledRange,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .template_source import WorkbookTemplateSource
from .theme import FORM_FONT_FAMILY, StyleRole


def add_form_workbook[M: (SheetExportMetadata, SheetReviewMetadata)](
    plan: SheetExportPlan[M],
    snapshot: RegistrySnapshot,
    *,
    revision: CalculationRevision | None = None,
    producer_snapshot: FilingProducerSnapshot | None = None,
) -> SheetExportPlan[M]:
    """Add a complete registry-declared form, retaining original cell addresses.

    Scenario plans link to their existing inputs/calculations. Saved review
    plans are refused until their exact registry identity and value mapping
    can be verified. Missing figures stay visibly unknown. Generated layout
    provenance is always disclosed.
    """
    if isinstance(plan.metadata, SheetReviewMetadata):
        raise CalcSheetsEngineError("saved review baseline requires verified registry identity and value mapping")
    if TabName.FORM in plan.tabs:
        raise CalcSheetsEngineError("workbook already contains a form projection")
    if (
        plan.metadata.modelo_id != snapshot.modelo.id
        or plan.metadata.revision_id != snapshot.revision.id
        or plan.metadata.filing_year != snapshot.filing_year
        or plan.metadata.period.code != snapshot.period
    ):
        raise CalcSheetsEngineError("form snapshot does not match workbook coordinate")
    layouts = snapshot.revision.form_layouts
    if len(layouts) != 1:
        raise CalcSheetsEngineError("form projection requires exactly one declared revision layout")
    layout = layouts[0]
    _validate_layout(layout, snapshot.revision)
    if plan.metadata.registry_sha != registry_sha(snapshot):
        raise CalcSheetsEngineError("form snapshot content does not match workbook registry identity")
    if revision is not None and revision.registry_snapshot_ref != snapshot.snapshot_ref:
        raise CalcSheetsEngineError("saved repeating rows belong to another registry coordinate")

    def context(block: FormContextFieldBlock) -> ModeloFormScalar:
        return form_context_value(snapshot, block, producer_snapshot=producer_snapshot, revision=revision)

    def records(block: FormRepeatingGroupBlock) -> tuple[bool, tuple[ModeloFormRepeatingRow, ...]]:
        return saved_form_records(
            snapshot=snapshot,
            revision=revision,
            block=block,
            column_casillas=tuple(column.casilla_id for column in block.columns),
        )

    bindings = _binding_addresses(plan, snapshot.revision)
    return _project_form(
        human_workbook(plan, snapshot),
        snapshot.revision,
        str(snapshot.modelo.id),
        snapshot.filing_period or plan.metadata.period,
        layout,
        bindings,
        context,
        records,
    )


def add_template_preview_form(
    plan: SheetExportPlan[SheetTemplatePreviewMetadata],
    source: WorkbookTemplateSource,
    *,
    illustrative_producer: FilingProducerSnapshot | None = None,
) -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    """Render a fictional template without acquiring filing or saved-revision authority."""
    if illustrative_producer is not None and str(illustrative_producer.modelo) != str(source.modelo_id):
        raise CalcSheetsEngineError("illustrative form context belongs to another modelo")
    if TabName.FORM in plan.tabs:
        raise CalcSheetsEngineError("workbook already contains a form projection")
    if len(source.revision.form_layouts) != 1:
        raise CalcSheetsEngineError("form projection requires exactly one declared revision layout")
    layout = source.revision.form_layouts[0]
    _validate_layout(layout, source.revision)
    bindings = _binding_addresses(plan, source.revision)
    # This entry validates the full preview coordinate and digest before rendering.
    plan = human_template_preview(plan, source)
    illustrative_values = filing_producer_values(illustrative_producer) if illustrative_producer is not None else {}

    def context(block: FormContextFieldBlock) -> ModeloFormScalar:
        field = resolve_form_context_field(source.revision, block)
        frame = source.preview_frame
        if field.draft_attribute is ExportDraftAttribute.FILING_YEAR:
            return frame.filing_year
        if field.draft_attribute is ExportDraftAttribute.PERIOD_CODE:
            return str(frame.code)
        if isinstance(frame, Period) and frame.has_date_span():
            if field.draft_attribute is ExportDraftAttribute.PERIOD_START_DATE:
                return frame.start_date
            if field.draft_attribute is ExportDraftAttribute.PERIOD_END_DATE:
                return frame.end_date
        value = illustrative_values.get(field.producer_key) if field.producer_key else None
        if value is None or isinstance(value, (str, bool, int, Decimal, date)):
            return value
        raise CalcSheetsEngineError("illustrative form context is not a supported scalar")

    return _project_form(
        plan,
        source.revision,
        str(source.modelo_id),
        source.preview_frame,
        layout,
        bindings,
        context,
        lambda block: (False, ()),
    )


def _saved_cell_value(value: ModeloFormScalar) -> str | Decimal | bool | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    return value


def add_saved_review_form(
    plan: SheetExportPlan[SheetReviewMetadata],
    saved: ReviewSavedForm,
) -> SheetExportPlan[SheetReviewMetadata]:
    """Render original declared geometry with literal saved values and no recomputation."""
    if plan.metadata.kind != "calculation" or TabName.FORM in plan.tabs:
        raise CalcSheetsEngineError("saved form requires one calculation review without an existing form")
    snapshot = saved.rendering.registry_snapshot
    if len(snapshot.revision.form_layouts) != 1:
        raise CalcSheetsEngineError("saved form requires exactly one captured layout")
    layout = snapshot.revision.form_layouts[0]
    _validate_layout(layout, snapshot.revision)
    contexts = {item.id: item.value for item in saved.contexts}
    records = {item.block_id: (item.known, item.rows) for item in saved.records}
    return _project_form(
        plan,
        snapshot.revision,
        str(snapshot.modelo.id),
        snapshot.filing_period or Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        layout,
        {},
        lambda block: contexts.get(block.id),
        lambda block: records.get(block.id, (False, ())),
        saved_form=saved,
    )


def _binding_addresses[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    registry_revision: ModeloRevision,
) -> dict[str, SheetCellAddress]:
    binding_addresses = {
        str(cell.value): SheetCellAddress.at(cell.address.tab, cell.address.row, 4)
        for cell in plan.value_cells
        if cell.address.tab is TabName.ENTRADAS
        and cell.address.column == 3
        and cell.value in {binding.id for binding in registry_revision.bindings}
    }
    input_addresses = {
        cell.casilla_id: cell.address
        for cell in plan.value_cells
        if cell.casilla_id is not None and cell.address.tab is TabName.ENTRADAS
    }
    for binding in registry_revision.bindings:
        if binding.id in binding_addresses or not isinstance(binding.provider, ManualInputProvider):
            continue
        owners = {casilla.id for casilla in registry_revision.casillas if casilla.binding == binding.id}
        if binding.provider.casilla_id is not None:
            owners.add(binding.provider.casilla_id)
        addresses = {input_addresses[key].qualified(): input_addresses[key] for key in owners if key in input_addresses}
        if len(addresses) == 1:
            binding_addresses[binding.id] = next(iter(addresses.values()))
    return binding_addresses


def _project_form[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    registry_revision: ModeloRevision,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    layout: FormLayoutDefinition,
    bindings: dict[str, SheetCellAddress],
    context: Callable[[FormContextFieldBlock], ModeloFormScalar],
    records: Callable[[FormRepeatingGroupBlock], tuple[bool, tuple[ModeloFormRepeatingRow, ...]]],
    *,
    saved_form: ReviewSavedForm | None = None,
) -> SheetExportPlan[M]:
    builder = _FormBuilder(plan, registry_revision, modelo_id, frame, layout, context, records, saved_form=saved_form)
    builder.binding_addresses = bindings
    builder.render()
    roles = {
        StyleRole.INPUT: StyleRole.FORM_INPUT,
        StyleRole.COMPUTED: StyleRole.FORM_COMPUTED,
        StyleRole.RESULT: StyleRole.FORM_RESULT,
        StyleRole.SECTION_BANNER: StyleRole.FORM_SECTION,
        StyleRole.HEADER: StyleRole.FORM_SECTION,
        StyleRole.BODY: StyleRole.FORM_LABEL,
    }
    updates = {
        "tabs": (TabName.FORM, *plan.tabs),
        "value_cells": (*plan.value_cells, *builder.values),
        "formula_cells": (*builder.guarded_calculations(), *builder.formulas),
        "merged_ranges": (*plan.merged_ranges, *builder.merges),
        "row_heights": (*plan.row_heights, *builder.heights),
        "styled_ranges": (
            *(r.model_copy(update={"role": roles.get(r.role, r.role)}) for r in plan.styled_ranges),
            *builder.styles,
        ),
        "font_family": FORM_FONT_FAMILY,
        "number_formats": (*plan.number_formats, *builder.formats),
        "column_widths": (
            *plan.column_widths,
            *(
                SheetColumnWidth(tab=TabName.FORM, column=i, width=width)
                for i, width in enumerate(builder.column_widths, 1)
            ),
        ),
        "frozen_views": (*plan.frozen_views, SheetFrozenView(tab=TabName.FORM, frozen_rows=4)),
        "protected_ranges": (
            *plan.protected_ranges,
            SheetProtectedRange(
                tab=TabName.FORM,
                start_row=1,
                end_row=builder.row,
                start_column=1,
                end_column=len(builder.column_widths),
                description="Formulario de consulta; los datos se modifican en las hojas de origen.",
            ),
        ),
    }
    return type(plan).model_validate({**dict(plan), **updates})


def _validate_layout(layout: FormLayoutDefinition, registry_revision: ModeloRevision) -> None:
    if layout.revision_id != registry_revision.id:
        raise CalcSheetsEngineError("form layout belongs to another revision")
    expected = {c.id for c in registry_revision.casillas}
    declared = [p.casilla_id for p in layout.placements]
    if len(declared) != len(set(declared)) or set(declared) != expected:
        raise CalcSheetsEngineError("form placements must account for every revision casilla exactly once")
    shown: list[str] = []
    positions: dict[str, list[tuple[str, str]]] = {}
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                before = len(shown)
                if isinstance(block, FormFieldBlock) and block.casilla_id is not None:
                    shown.append(block.casilla_id)
                elif isinstance(block, FormGridBlock):
                    shown.extend(cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id)
                elif isinstance(block, FormRepeatingGroupBlock):
                    shown.extend(column.casilla_id for column in block.columns if column.casilla_id)
                    if any(column.export_field_id is not None for column in block.columns):
                        resolve_form_projection_fields(registry_revision, block)
                for casilla_id in shown[before:]:
                    positions.setdefault(casilla_id, []).append((page.id, section.id))
    on_form = {p.casilla_id for p in layout.placements if p.kind is FormPlacementKind.ON_FORM}
    placements = {p.casilla_id: p for p in layout.placements}
    bad_alias = any(
        len(locations) != len(set(locations))
        or any(
            position not in {(a.page_id, a.section_id) for a in placements[key].aliases} for position in locations[1:]
        )
        for key, locations in positions.items()
        if key in placements
    )
    if set(shown) != on_form or bad_alias:
        raise CalcSheetsEngineError("form blocks contain missing, unknown, or duplicate casilla placements")


class _FormBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)]:
    def __init__(
        self,
        plan: SheetExportPlan[M],
        registry_revision: ModeloRevision,
        modelo_id: str,
        frame: Period | SheetAdministrativeFrame,
        layout: FormLayoutDefinition,
        context: Callable[[FormContextFieldBlock], ModeloFormScalar],
        records: Callable[[FormRepeatingGroupBlock], tuple[bool, tuple[ModeloFormRepeatingRow, ...]]],
        *,
        saved_form: ReviewSavedForm | None = None,
    ) -> None:
        self.plan = plan
        self.registry_revision = registry_revision
        self.modelo_id = modelo_id
        self.frame = frame
        self.layout = layout
        self.context = context
        self.records = records
        self.saved_form = saved_form
        self.saved_labels = {label.key: label.text for label in saved_form.rendering.labels} if saved_form else None
        self.casillas = {c.id: c for c in registry_revision.casillas}
        self.compact_dates = compact_date_casillas(registry_revision)
        result = declaration_result_casillas(modelo_id, registry_revision)
        self.result_ids: frozenset[str] = frozenset(result.casilla_ids) if result is not None else frozenset()
        self.placements = {p.casilla_id: p for p in layout.placements}
        self.sources: dict[str, SheetValueCell | SheetFormulaCell] = {}
        for cell in (*plan.value_cells, *plan.formula_cells):
            if cell.casilla_id is not None and cell.address.tab in (TabName.ENTRADAS, TabName.CALCULOS):
                if cell.casilla_id in self.sources:
                    raise CalcSheetsEngineError("form source contains ambiguous duplicate casilla values")
                self.sources[cell.casilla_id] = cell
        if saved_form is not None:
            self.sources = {
                item.id: SheetValueCell(
                    address=SheetCellAddress.at(TabName.CALCULOS, index, 4),
                    value=_saved_cell_value(item.value),
                    casilla_id=item.id,
                    role="source_value",
                )
                for index, item in enumerate(saved_form.scalars, 1)
                if item.id in self.casillas
            }
        self.address_sources = {c.address.qualified(): c for c in (*plan.value_cells, *plan.formula_cells)}
        self.values: list[SheetValueCell] = []
        self.formulas: list[SheetFormulaCell] = []
        self.merges: list[SheetMergedRange] = []
        self.heights: list[SheetRowHeight] = []
        self.styles: list[SheetStyledRange] = []
        self.formats: list[SheetNumberFormat] = []
        self.row = 2
        self.binding_addresses: dict[str, SheetCellAddress] = {}
        widest_grid = max(
            (
                len(grid.columns)
                for page in layout.pages
                for section in page.sections
                for block in section.blocks
                for grid in (
                    (block,)
                    if isinstance(block, FormGridBlock)
                    else block.grids
                    if isinstance(block, FormRepeatingGroupBlock)
                    else ()
                )
            ),
            default=0,
        )
        self.column_widths: tuple[int, ...] = (
            (3, 12, 12, 12, 12, *(width for _ in range(widest_grid) for width in (9, 18)), 3)
            if widest_grid > 3
            else (3, 12, 12, 12, 12, 12, 18, 12, 18, 10, 18, 10, 3)
            if widest_grid
            else (3, 12, 12, 12, 12, 12, 12, 12, 7, 10, 10, 10, 3)
        )

    def localized(self, key: str | None) -> str | None:
        """Use captured original wording for a saved form, never today's catalogue."""
        if key is None:
            return None
        return self.saved_labels.get(key) if self.saved_labels is not None else lookup_translation(key, locale="es")

    def casilla_label(self, casilla_id: str) -> str:
        """Resolve one saved label from the original immutable presentation metadata."""
        casilla = self.casillas[casilla_id]
        if self.saved_labels is None:
            return casilla.label
        return next(
            (self.saved_labels[key] for key in casilla.localization_keys if key in self.saved_labels), "Dato guardado"
        )

    def text(self, text: str | Decimal | bool | None, column: int = 2) -> None:
        address = SheetCellAddress.at(TabName.FORM, self.row, column)
        self.values.append(SheetValueCell(address=address, value=text, role="label"))
        if isinstance(text, str):
            self.formats.append(SheetNumberFormat(address=address, data_type="text", pattern="@"))
        elif isinstance(text, Decimal):
            pattern = numeric_format("decimal")
            if pattern is not None:
                self.formats.append(SheetNumberFormat(address=address, data_type=pattern[0], pattern=pattern[1]))

    def span(self, start: int, end: int, role: StyleRole, *, boxed: bool = False) -> None:
        if start < end:
            self.merges.append(
                SheetMergedRange(
                    tab=TabName.FORM, start_row=self.row, end_row=self.row, start_column=start, end_column=end
                )
            )
        self.styles.append(
            SheetStyledRange(
                tab=TabName.FORM,
                start_row=self.row,
                end_row=self.row,
                start_column=start,
                end_column=end,
                role=role,
                wrap=True,
                boxed=boxed or role is StyleRole.FORM_SECTION,
            )
        )

    def line(self, text: str, role: StyleRole = StyleRole.FORM_LABEL) -> None:
        self.text(text)
        self.span(2, len(self.column_widths) - 1, role)
        self.heights.append(
            SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=max(28, 20 * (1 + len(text) // 110)))
        )
        self.row += 1

    def value(
        self, casilla_id: str, column: int, end: int, *, constant: str | None = None, decimals: int | None = None
    ) -> None:
        source = self.sources.get(casilla_id)
        address = SheetCellAddress.at(TabName.FORM, self.row, column)
        if constant is not None:
            self.text(Decimal(constant).scaleb(-decimals) if decimals is not None else constant, column)
        elif source is None:
            self.text("Sin dato", column)
        elif self.saved_form is not None and isinstance(source, SheetValueCell):
            self.text(source.value, column)
        else:
            reference = source.address.qualified()
            leaves = self.input_leaves(source, frozenset())
            guards = ",".join(f"ISBLANK({leaf})" for leaf in sorted(leaves))
            guard = f"OR({guards})" if len(leaves) > 1 else guards or f"ISBLANK({reference})"
            if isinstance(source, SheetFormulaCell) and source.missing_input_condition is not None:
                guard = source.missing_input_condition
            displayed = compact_date_expression(reference) if casilla_id in self.compact_dates else reference
            self.formulas.append(
                SheetFormulaCell(
                    address=address,
                    formula=f'IF({guard},"Sin dato",{displayed})',
                    casilla_id=casilla_id,
                    rounding_rule=SheetRoundingRule.NONE,
                )
            )
        role = StyleRole.FORM_COMPUTED
        if isinstance(source, SheetValueCell) and source.role == "operator_input":
            role = StyleRole.FORM_INPUT
        if casilla_id in self.result_ids:
            role = StyleRole.FORM_RESULT
        self.span(column, end, role, boxed=True)
        if source is not None:
            for directive in self.plan.number_formats:
                if directive.address == source.address:
                    self.formats.append(directive.model_copy(update={"address": address}))
        elif constant is not None:
            pattern = numeric_format(self.casillas[casilla_id].data_type)
            if pattern is not None:
                self.formats.append(SheetNumberFormat(address=address, data_type=pattern[0], pattern=pattern[1]))

    def guarded_calculations(self) -> tuple[SheetFormulaCell, ...]:
        """Keep supporting calculations unknown when their scalar inputs are blank.

        The canonical arithmetic remains the populated branch. The same
        transitive-input policy already used by the form applies to every
        visible calculation, so supporting sheets cannot imply a known zero.
        """
        guarded: list[SheetFormulaCell] = []
        for cell in self.plan.formula_cells:
            if cell.missing_input_condition is not None:
                guarded.append(
                    cell.model_copy(update={"formula": f'IF({cell.missing_input_condition},"Sin dato",{cell.formula})'})
                )
                continue
            leaves = sorted(self.input_leaves(cell, frozenset()))
            if not leaves:
                guarded.append(cell)
                continue
            checks = ",".join(f"ISBLANK({leaf})" for leaf in leaves)
            condition = f"OR({checks})" if len(leaves) > 1 else checks
            guarded.append(cell.model_copy(update={"formula": f'IF({condition},"Sin dato",{cell.formula})'}))
        return tuple(guarded)

    def input_leaves(
        self,
        source: SheetValueCell | SheetFormulaCell,
        visited: frozenset[str],
    ) -> set[str]:
        """Conservatively require every transitive scalar input, including branch inputs.

        This projection does not resolve missing inputs to spreadsheet zero.
        Dynamic guards also react when an initially populated input is cleared.
        """
        address = source.address.qualified()
        if address in visited:
            raise CalcSheetsEngineError("form source formula dependency cycle")
        if isinstance(source, SheetValueCell):
            return {address} if source.role in ("operator_input", "parameter_value") or source.value is None else set()
        leaves: set[str] = set()
        for reference in re.findall(r"'[^']+'!\$?[A-Z]+\$?[0-9]+", source.formula):
            dependency = self.address_sources.get(reference.replace("$", ""))
            if dependency is not None:
                leaves.update(self.input_leaves(dependency, visited | {address}))
        return leaves

    def choices(self, block: FormFieldBlock) -> None:
        """Show mutually exclusive marks from one source, preserving unknown values."""
        if block.casilla_id is None:
            raise CalcSheetsEngineError("form choices require a casilla")
        casilla = next(c for c in self.registry_revision.casillas if c.id == block.casilla_id)
        domain = casilla.constraints.enum if casilla.constraints is not None else None
        if casilla.data_type.value != "text" or domain is None or any(c.value not in domain for c in block.choices):
            raise CalcSheetsEngineError("form choices require values in the casilla's closed text domain")
        source = self.sources.get(block.casilla_id)
        for choice in block.choices:
            self.text(self.localized(choice.heading_key) or choice.official_heading or "Opción")
            self.span(2, 8, StyleRole.FORM_LABEL)
            if source is None:
                self.text("Sin dato", 10)
            elif self.saved_form is not None and isinstance(source, SheetValueCell):
                self.text("Sin dato" if source.value is None else "X" if source.value == choice.value else "", 10)
            else:
                reference = source.address.qualified()
                literal = choice.value.replace('"', '""')
                allowed = ",".join(f'EXACT({reference},"{value.replace(chr(34), chr(34) * 2)}")' for value in domain)
                self.formulas.append(
                    SheetFormulaCell(
                        address=SheetCellAddress.at(TabName.FORM, self.row, 10),
                        formula=(
                            f'IF(ISBLANK({reference}),"Sin dato",IF(NOT(OR({allowed})),"Valor no válido",'
                            f'IF(EXACT({reference},"{literal}"),"X","")))'
                        ),
                        casilla_id=block.casilla_id,
                        rounding_rule=SheetRoundingRule.NONE,
                    )
                )
            self.span(10, 12, StyleRole.FORM_COMPUTED, boxed=True)
            self.row += 1

    def field(self, casilla_id: str, *, constant: str | None = None, decimals: int | None = None) -> None:
        self.text(self.casilla_label(casilla_id))
        self.span(2, 8, StyleRole.FORM_LABEL)
        self.text(str(self.placements[casilla_id].box_number or ""), 9)
        self.span(9, 9, StyleRole.CASILLA, boxed=True)
        self.value(casilla_id, 10, 12, constant=constant, decimals=decimals)
        self.heights.append(
            SheetRowHeight(
                tab=TabName.FORM,
                row=self.row,
                height_pixels=max(30, 18 * (1 + len(self.casilla_label(casilla_id)) // 65)),
            )
        )
        self.row += 1

    def binding(self, binding_id: str) -> None:
        if binding_id not in {b.id for b in self.registry_revision.bindings}:
            raise CalcSheetsEngineError("form references an unknown binding")
        address = self.binding_addresses.get(binding_id)
        if address is None:
            owners = [c for c in self.registry_revision.casillas if c.binding == binding_id]
            if len(owners) == 1:
                self.field(owners[0].id)
                return
            raise CalcSheetsEngineError("form binding has no unambiguous human-labelled source cell")
        label_address = SheetCellAddress.at(address.tab, address.row, 3)
        label_cell = self.address_sources[label_address.qualified()]
        if not isinstance(label_cell, SheetValueCell) or not isinstance(label_cell.value, str):
            raise CalcSheetsEngineError("form binding source has no human label")
        self.text(label_cell.value)
        self.span(2, 8, StyleRole.FORM_LABEL)
        self.binding_value(binding_id, 9, 12)
        self.row += 1

    def binding_value(self, binding_id: str, column: int, end: int, *, readonly: bool = False) -> None:
        """Link a declared binding to its existing value without inventing a zero."""
        if binding_id not in {binding.id for binding in self.registry_revision.bindings}:
            raise CalcSheetsEngineError("form references an unknown binding")
        if self.saved_form is not None:
            bindings = {item.id: item.value for item in self.saved_form.bindings}
            value = bindings.get(binding_id)
            if value is None:
                owners = [casilla.id for casilla in self.casillas.values() if casilla.binding == binding_id]
                source = self.sources.get(owners[0]) if len(owners) == 1 else None
                value = source.value if isinstance(source, SheetValueCell) else None
            self.text(_saved_cell_value(value) if value is not None else "Sin dato", column)
            self.span(column, end, StyleRole.FORM_COMPUTED, boxed=True)
            return
        address = self.binding_addresses.get(binding_id)
        if address is None:
            owners = [casilla for casilla in self.casillas.values() if casilla.binding == binding_id]
            if len(owners) != 1 or owners[0].id not in self.sources:
                raise CalcSheetsEngineError("form binding has no unambiguous source cell")
            address = self.sources[owners[0].id].address
        source = self.address_sources.get(address.qualified())
        if source is None:
            raise CalcSheetsEngineError("form binding source cell is missing")
        leaves = self.input_leaves(source, frozenset())
        guards = ",".join(f"ISBLANK({leaf})" for leaf in sorted(leaves))
        reference = address.qualified()
        guard = f"OR({guards})" if len(leaves) > 1 else guards or f"ISBLANK({reference})"
        if isinstance(source, SheetFormulaCell) and source.missing_input_condition is not None:
            guard = source.missing_input_condition
        target = SheetCellAddress.at(TabName.FORM, self.row, column)
        self.formulas.append(
            SheetFormulaCell(
                address=target,
                formula=f'IF({guard},"Sin dato",{reference})',
                casilla_id=None,
                rounding_rule=SheetRoundingRule.NONE,
            )
        )
        self.span(column, end, StyleRole.FORM_COMPUTED if readonly else StyleRole.FORM_INPUT, boxed=True)
        for directive in self.plan.number_formats:
            if directive.address == address:
                self.formats.append(directive.model_copy(update={"address": target}))

    def grid(self, block: FormGridBlock, *, record_values: dict[str, ModeloFormScalar] | None = None) -> None:
        # A declared row is one row across every column. Splitting the columns
        # into vertical chunks severs the relationships in official tables.
        headings = [self.localized(column.heading_key) or column.official_heading for column in block.columns]
        if any(not heading for heading in headings):
            raise CalcSheetsEngineError("form grid requires an authored column heading")
        row_heading = self.localized(block.row_heading_key) or block.official_row_heading or "Concepto"
        self.text(row_heading)
        self.span(2, 5, StyleRole.FORM_SECTION)
        for index, heading in enumerate(headings):
            start = 6 + index * 2
            self.text(heading, start)
            self.span(start, start + 1, StyleRole.FORM_SECTION)
        self.heights.append(
            SheetRowHeight(
                tab=TabName.FORM,
                row=self.row,
                height_pixels=min(
                    409, max(44, 18 * (1 + max(len(heading or "") for heading in [row_heading, *headings]) // 24))
                ),
            )
        )
        self.row += 1
        for row in block.rows:
            heading = self.localized(row.heading_key) or row.official_heading
            if not heading:
                raise CalcSheetsEngineError("form grid requires an authored row heading")
            self.text(heading)
            self.span(2, 5, StyleRole.FORM_LABEL)
            text_lines = sum(max(1, len(wrap(line, width=44))) for line in heading.splitlines())
            for column_index, cell in enumerate(row.cells):
                start = 6 + column_index * 2
                visible_value: ModeloFormScalar = None
                text_width = sum(self.column_widths[start - 1 : start + 1]) - 2
                if cell.casilla_id:
                    text_width = self.column_widths[start] - 2
                    self.text(str(self.placements[cell.casilla_id].box_number or ""), start)
                    self.span(start, start, StyleRole.CASILLA, boxed=True)
                    if record_values is None:
                        self.value(
                            cell.casilla_id, start + 1, start + 1, constant=cell.literal, decimals=cell.literal_decimals
                        )
                        source = self.sources.get(cell.casilla_id)
                        if isinstance(source, SheetValueCell):
                            visible_value = source.value
                    else:
                        self.record_value(cell.casilla_id, record_values[cell.casilla_id], start + 1, start + 1)
                        visible_value = record_values[cell.casilla_id]
                elif cell.kind is FormCellKind.DESIGN_CONSTANT:
                    visible_value = cell.literal
                    self.text(
                        Decimal(cell.literal).scaleb(-cell.literal_decimals)
                        if cell.literal_decimals is not None and cell.literal is not None
                        else cell.literal,
                        start,
                    )
                    self.span(start, start + 1, StyleRole.FORM_COMPUTED, boxed=True)
                elif cell.kind is FormCellKind.BINDING_INPUT:
                    if cell.binding_id is None:
                        raise CalcSheetsEngineError("form grid binding cell has no declared binding")
                    self.binding_value(cell.binding_id, start, start + 1)
                    address = self.binding_addresses.get(cell.binding_id)
                    source = self.address_sources.get(address.qualified()) if address is not None else None
                    if isinstance(source, SheetValueCell):
                        visible_value = source.value
                if isinstance(visible_value, str):
                    text_lines = max(
                        text_lines,
                        sum(max(1, len(wrap(line, width=max(1, text_width)))) for line in visible_value.splitlines()),
                    )
            self.heights.append(
                SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=min(409, max(44, 18 * text_lines + 8)))
            )
            self.row += 1

    def record_value(
        self, casilla_id: str | None, value: ModeloFormScalar, column: int, end: int, *, data_type: str | None = None
    ) -> None:
        """Render a saved record value; scalar sources contribute formatting only."""
        self.text(
            value.isoformat()
            if isinstance(value, date)
            else value
            if value is not None and (isinstance(value, bool) or not isinstance(value, int))
            else Decimal(value)
            if isinstance(value, int)
            else "Sin dato",
            column,
        )
        self.span(column, end, StyleRole.FORM_COMPUTED, boxed=True)
        if isinstance(value, Decimal | int) and not isinstance(value, bool):
            casilla = self.casillas.get(casilla_id) if casilla_id else None
            pattern = numeric_format(data_type or (casilla.data_type if casilla is not None else "decimal"))
            if pattern is not None:
                self.formats.append(
                    SheetNumberFormat(
                        address=SheetCellAddress.at(TabName.FORM, self.row, column),
                        data_type=pattern[0],
                        pattern=pattern[1],
                    )
                )

    def repeating(self, block: FormRepeatingGroupBlock) -> None:
        known, saved_rows = self.records(block)
        projection_types = (
            {field.id: str(field.data_type) for field in resolve_form_projection_fields(self.registry_revision, block)}
            if any(column.export_field_id is not None for column in block.columns)
            else {}
        )
        if known:
            if len(saved_rows) > min(block.max_rows or 1000, 1000):
                raise CalcSheetsEngineError("repeating form exceeds its bounded row capacity")
            if not saved_rows:
                self.line("No hay registros en el detalle guardado.")
            gridded = {cell.casilla_id for grid in block.grids for row in grid.rows for cell in row.cells}
            for record in saved_rows:
                self.line(f"Registro {record.index}", StyleRole.FORM_SECTION)
                record_values = {
                    column.casilla_id: value
                    for column, value in zip(block.columns, record.values, strict=True)
                    if column.casilla_id is not None
                }
                for column, value in zip(block.columns, record.values, strict=True):
                    if column.casilla_id in gridded:
                        continue
                    label = (
                        self.localized(column.heading_key)
                        or column.official_heading
                        or (self.casilla_label(column.casilla_id) if column.casilla_id else "Dato del registro")
                    )
                    box_number = self.placements[column.casilla_id].box_number if column.casilla_id else None
                    self.text(label)
                    self.span(2, 8, StyleRole.FORM_LABEL)
                    if box_number:
                        self.text(str(box_number), 9)
                        self.span(9, 9, StyleRole.CASILLA, boxed=True)
                    self.record_value(
                        column.casilla_id,
                        value,
                        10 if box_number else 9,
                        12,
                        data_type=projection_types.get(column.export_field_id) if column.export_field_id else None,
                    )
                    self.heights.append(SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=32))
                    self.row += 1
                for grid in block.grids:
                    self.grid(grid, record_values=record_values)
            return
        # Row sets expose binding identity, never an implicit positional join
        # to a differently shaped export record.
        row_sets = [r for r in self.plan.row_sets if any(c.binding == block.binding_id for c in r.columns)]
        if len(row_sets) > 1:
            raise CalcSheetsEngineError("repeating form binding has ambiguous source row sets")
        labels = [
            column.official_heading or (self.casilla_label(column.casilla_id) if column.casilla_id else f"Columna {i}")
            for i, column in enumerate(block.columns, 1)
        ]
        # A record can have dozens of fields. Preserve each heading in its own
        # row rather than joining them into an unreadable, oversized banner.
        for label in labels:
            self.line(label)
        if not row_sets:
            self.line("Sin registros aportados a esta vista. Consulte el detalle de origen.")
            return
        row_set = row_sets[0]
        source_columns = {c.header_address.column: c.header_label for c in row_set.columns}
        next_headers = [
            r.header_row for r in self.plan.row_sets if r.tab == row_set.tab and r.header_row > row_set.header_row
        ]
        end = min(next_headers) if next_headers else 1_000_001
        rows: dict[int, list[SheetValueCell]] = {}
        for cell in self.plan.value_cells:
            if (
                cell.address.tab == row_set.tab
                and row_set.first_data_row <= cell.address.row < end
                and cell.address.column in source_columns
            ):
                rows.setdefault(cell.address.row, []).append(cell)
        limit = min(block.max_rows or 1000, 1000)
        if len(rows) > limit:
            raise CalcSheetsEngineError("repeating form exceeds its bounded row capacity")
        if not rows:
            self.line("Sin registros aportados a esta vista. Consulte el detalle de origen.")
        for index, cells in enumerate(rows.values(), 1):
            self.line(f"Registro {index}", StyleRole.FORM_SECTION)
            for cell in cells:
                self.text(source_columns[cell.address.column])
                self.span(2, 8, StyleRole.FORM_LABEL)
                self.text(cell.value if cell.value is not None else "Sin dato", 9)
                self.span(9, 12, StyleRole.FORM_COMPUTED, boxed=True)
                self.row += 1

    def context_field(self, block: FormContextFieldBlock) -> None:
        """Show only the explicitly declared immutable filing fact."""
        field = resolve_form_context_field(self.registry_revision, block)
        label = self.localized(block.heading_key) or block.official_heading or "Dato del formulario"
        self.text(label)
        value_column = 10 if block.box_number else 9
        if block.box_number:
            self.text(str(block.box_number), 9)
            self.span(9, 9, StyleRole.CASILLA, boxed=True)
        if field.binding is not None:
            self.span(2, 8, StyleRole.FORM_LABEL)
            self.binding_value(str(field.binding), value_column, 12, readonly=True)
            self.heights.append(SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=32))
            self.row += 1
            return
        value = self.context(block)
        choice = form_context_choice(block, value)
        if choice is not None:
            value = self.localized(choice.heading_key) or choice.official_heading or "Opción"
        self.span(2, 8, StyleRole.FORM_LABEL)
        if value is None:
            shown: str | Decimal = "Sin dato"
        elif isinstance(value, bool):
            shown = tr(VALUE_TRUE_LOCALE_KEY if value else VALUE_FALSE_LOCALE_KEY, locale="es")
        elif isinstance(value, date):
            shown = value.isoformat()
        elif isinstance(value, int):
            shown = Decimal(value)
        else:
            shown = value
        self.text(shown, value_column)
        if field.draft_attribute is ExportDraftAttribute.FILING_YEAR and isinstance(shown, Decimal):
            self.formats.append(
                SheetNumberFormat(
                    address=SheetCellAddress.at(TabName.FORM, self.row, value_column),
                    data_type="integer",
                    pattern="0",
                )
            )
        self.span(value_column, 12, StyleRole.FORM_COMPUTED, boxed=True)
        self.heights.append(SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=32))
        self.row += 1

    def conditional_checks(self) -> None:
        """Expose supported categorical requirements without claiming complete verification."""
        if self.saved_form is not None:
            return
        heading_shown = False
        for predicate in self.registry_revision.verification_predicates:
            parsed = parse_verification_predicate_expression(predicate.expression)
            if (
                predicate.finding_kind.value != "BLOCKING_RULE"
                or parsed is None
                or parsed.operator
                not in (
                    VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO,
                    VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO,
                )
            ):
                continue
            antecedent, consequent = parsed.casilla_ids
            trigger, required = self.sources.get(antecedent), self.sources.get(consequent)
            if trigger is None or required is None:
                raise CalcSheetsEngineError("conditional form check has no source cell")
            if not heading_shown:
                self.row += 1
                self.line("Comprobaciones parciales de los datos", StyleRole.FORM_SECTION)
                heading_shown = True
            label = self.casilla_label(antecedent)
            for page in self.layout.pages:
                for section in page.sections:
                    for block in section.blocks:
                        if isinstance(block, FormFieldBlock) and block.casilla_id == antecedent:
                            for choice in block.choices:
                                if choice.value == parsed.literal:
                                    label = self.localized(choice.heading_key) or choice.official_heading or label
            self.text(f"{label}: {self.casilla_label(consequent)}")
            self.span(2, 8, StyleRole.FORM_LABEL)
            source, target = trigger.address.qualified(), required.address.qualified()
            literal = parsed.literal.replace('"', '""')
            requirement = (
                f'IF(ISBLANK({target}),"Falta dato",IF(AND(ISNUMBER({target}),{target}=0),'
                '"Cero indicado","Debe ser cero"))'
                if parsed.operator is VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO
                else f'IF(AND(ISNUMBER({target}),{target}<>0),"Dato aportado","Falta dato")'
            )
            self.formulas.append(
                SheetFormulaCell(
                    address=SheetCellAddress.at(TabName.FORM, self.row, 10),
                    formula=(
                        f'IF(ISBLANK({source}),"Sin dato",IF(EXACT({source},"{literal}"),{requirement},"No aplica"))'
                    ),
                    casilla_id=None,
                    rounding_rule=SheetRoundingRule.NONE,
                )
            )
            self.span(10, 12, StyleRole.FORM_COMPUTED, boxed=True)
            self.row += 1

    def render(self) -> None:
        period_suffix = (
            f" · {self.frame.code}" if isinstance(self.frame, Period) and self.frame.code != AD_HOC_PERIOD_CODE else ""
        )
        self.line(f"Modelo {self.modelo_id} · {self.frame.filing_year}{period_suffix}", StyleRole.TITLE)
        if isinstance(self.plan.metadata, SheetReviewMetadata):
            caption = self.plan.metadata.title + " · copia de valores guardados; no válida para presentar"
        elif isinstance(self.plan.metadata, SheetTemplatePreviewMetadata):
            caption = "EJEMPLO FICTICIO · ejercicio y período ilustrativos · no válido para presentar"
        elif not isinstance(self.frame, Period):
            caption = tr("application.storage.calc_sheets.form.communication_caption", locale="es")
        elif not self.registry_revision.formulas:
            caption = tr("application.storage.calc_sheets.form.reported_data_caption", locale="es")
        else:
            caption = "Escenario de cálculo · edite los datos en las hojas de origen"
        self.line(caption)
        if self.layout.review.state is FormLayoutReviewState.GENERATED:
            self.line("Distribución generada desde el registro; pendiente de revisión visual del formulario oficial.")
        else:
            self.line("Distribución revisada. Documento de trabajo; no es un justificante de presentación.")
        for page_index, page in enumerate(self.layout.pages, 1):
            if (
                page.condition is FormPageCondition.PERIOD_RESTRICTED
                and isinstance(self.frame, Period)
                and self.frame.code not in page.condition_periods
            ):
                continue
            self.row += 1
            heading = self.localized(page.heading_key) or page.official_heading
            self.line(
                heading or f"Página {page_index}",
                StyleRole.TITLE,
            )
            if page.condition is not FormPageCondition.ALWAYS:
                descriptions = {
                    FormPageCondition.OPTIONAL_RECORD: "Página opcional; compruebe si corresponde.",
                    FormPageCondition.REQUIRES_POSITIVE_CASILLA: (
                        "Página condicionada a una casilla positiva; compruebe su aplicación."
                    ),
                    FormPageCondition.PERIOD_RESTRICTED: "Página aplicable a los períodos: "
                    + ", ".join(page.condition_periods),
                }
                self.line(descriptions[page.condition])
            for section_index, section in enumerate(page.sections, 1):
                self.line(
                    self.localized(section.heading_key) or section.official_heading or f"Apartado {section_index}",
                    StyleRole.FORM_SECTION,
                )
                for block in section.blocks:
                    if isinstance(block, FormFieldBlock):
                        if block.choices:
                            self.choices(block)
                        elif block.casilla_id:
                            self.field(
                                block.casilla_id, constant=block.design_constant, decimals=block.literal_decimals
                            )
                        elif block.binding_id:
                            self.binding(block.binding_id)
                    elif isinstance(block, FormGridBlock):
                        self.grid(block)
                    elif isinstance(block, FormRepeatingGroupBlock):
                        self.repeating(block)
                    elif isinstance(block, FormContextFieldBlock):
                        self.context_field(block)
                    else:
                        for binding_id in block.binding_ids:
                            self.binding(binding_id)
        for kind, title in (
            (FormPlacementKind.WORKING_FIGURE, "Datos auxiliares del cálculo"),
            (FormPlacementKind.UNPLACED, "Datos pendientes de ubicación en el formulario"),
        ):
            placements = [
                p
                for p in self.layout.placements
                if p.kind is kind and p.workbook_exclusion is None and not self.casillas[p.casilla_id].internal_only
            ]
            if placements:
                self.row += 1
                self.line(title, StyleRole.FORM_SECTION)
                for placement in placements:
                    self.field(placement.casilla_id)
        self.conditional_checks()


__all__ = ["add_form_workbook", "add_template_preview_form"]
