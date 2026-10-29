"""Scalar source and cell rendering for form workbooks.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from ...export.review_form_data import ReviewSavedForm
from ...modelo.settlement_casilla import declaration_result_casillas
from ...modelo.work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from .errors import CalcSheetsEngineError
from .form_geometry import form_column_widths, form_sources
from .form_value_presentation import compact_date_casillas, compact_date_expression
from .number_formats import numeric_format
from .records import (
    SheetAdministrativeFrame,
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetMergedRange,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetRoundingRule,
    SheetRowHeight,
    SheetStyledRange,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


def saved_cell_value(value: ModeloFormScalar) -> str | Decimal | bool | None:
    """Convert saved scalar values to transport cell values."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    return value


class FormCellBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)]:
    """Render the corresponding declared form phase."""

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
        """Render or initialize this form component."""
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
        self.sources = form_sources(plan, self.casillas, saved_form, saved_cell_value)
        self.address_sources = {c.address.qualified(): c for c in (*plan.value_cells, *plan.formula_cells)}
        self.values: list[SheetValueCell] = []
        self.formulas: list[SheetFormulaCell] = []
        self.merges: list[SheetMergedRange] = []
        self.heights: list[SheetRowHeight] = []
        self.styles: list[SheetStyledRange] = []
        self.formats: list[SheetNumberFormat] = []
        self.row: int = 2
        self.binding_addresses: dict[str, SheetCellAddress] = {}
        self.column_widths = form_column_widths(layout)

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
        """Render or initialize this form component."""
        address = SheetCellAddress.at(TabName.FORM, self.row, column)
        self.values.append(SheetValueCell(address=address, value=text, role="label"))
        if isinstance(text, str):
            self.formats.append(SheetNumberFormat(address=address, data_type="text", pattern="@"))
        elif isinstance(text, Decimal):
            pattern = numeric_format("decimal")
            if pattern is not None:
                self.formats.append(SheetNumberFormat(address=address, data_type=pattern[0], pattern=pattern[1]))

    def span(self, start: int, end: int, role: StyleRole, *, boxed: bool = False) -> None:
        """Render or initialize this form component."""
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
        """Render or initialize this form component."""
        self.text(text)
        self.span(2, len(self.column_widths) - 1, role)
        self.heights.append(
            SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=max(28, 20 * (1 + len(text) // 110)))
        )
        self.row += 1

    def _value_formula(
        self, source: SheetValueCell | SheetFormulaCell, casilla_id: str, address: SheetCellAddress
    ) -> None:
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

    def _value_style(
        self,
        source: SheetValueCell | SheetFormulaCell | None,
        casilla_id: str,
        address: SheetCellAddress,
        column: int,
        end: int,
        constant: str | None,
    ) -> None:
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

    def value(
        self, casilla_id: str, column: int, end: int, *, constant: str | None = None, decimals: int | None = None
    ) -> None:
        """Render or initialize this form component."""
        source = self.sources.get(casilla_id)
        address = SheetCellAddress.at(TabName.FORM, self.row, column)
        if constant is not None:
            self.text(Decimal(constant).scaleb(-decimals) if decimals is not None else constant, column)
        elif source is None:
            self.text("Sin dato", column)
        elif self.saved_form is not None and isinstance(source, SheetValueCell):
            self.text(source.value, column)
        else:
            self._value_formula(source, casilla_id, address)
        self._value_style(source, casilla_id, address, column, end, constant)

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
