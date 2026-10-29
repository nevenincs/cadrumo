"""Grid and repeating-record rendering for form workbooks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core.i18n.render import tr
from ....domain.calculations.registry.export_semantics import ExportDraftAttribute
from ....domain.calculations.registry.form_context import form_context_choice, resolve_form_context_field
from ....domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from ....domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
)
from ...modelo.value_presentation import VALUE_FALSE_LOCALE_KEY, VALUE_TRUE_LOCALE_KEY
from ...modelo.work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from .errors import CalcSheetsEngineError
from .form_grid_builder import FormGridBuilder
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetRowHeight,
    SheetRowSet,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


class FormRecordBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    FormGridBuilder[M]
):
    """Render the corresponding declared form phase."""

    def _saved_record_column(
        self, column: FormRepeatingColumn, value: ModeloFormScalar, projection_types: dict[str, str]
    ) -> None:
        label, box_number = self._record_label(column)
        self.text(label)
        self.span(2, 8, StyleRole.FORM_LABEL)
        if box_number is not None and box_number:
            self.text(box_number, 9)
            self.span(9, 9, StyleRole.CASILLA, boxed=True)
        self.record_value(
            column.casilla_id,
            value,
            10 if (box_number is not None and box_number) else 9,
            12,
            data_type=projection_types.get(column.export_field_id)
            if (column.export_field_id is not None and column.export_field_id)
            else None,
        )
        self.heights.append(SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=32))
        self.row += 1

    def _saved_record(
        self,
        block: FormRepeatingGroupBlock,
        record: ModeloFormRepeatingRow,
        gridded: set[str | None],
        projection_types: dict[str, str],
    ) -> None:
        self.line(f"Registro {record.index}", StyleRole.FORM_SECTION)
        record_values = {
            column.casilla_id: value
            for column, value in zip(block.columns, record.values, strict=True)
            if column.casilla_id is not None
        }
        for column, value in zip(block.columns, record.values, strict=True):
            if column.casilla_id in gridded:
                continue
            self._saved_record_column(column, value, projection_types)
        for grid in block.grids:
            self.grid(grid, record_values=record_values)

    def _saved_records(
        self,
        block: FormRepeatingGroupBlock,
        saved_rows: tuple[ModeloFormRepeatingRow, ...],
        projection_types: dict[str, str],
    ) -> None:
        if len(saved_rows) > min(block.max_rows or 1000, 1000):
            raise CalcSheetsEngineError("repeating form exceeds its bounded row capacity")
        if not saved_rows:
            self.line("No hay registros en el detalle guardado.")
        gridded = {cell.casilla_id for grid in block.grids for row in grid.rows for cell in row.cells}
        for record in saved_rows:
            self._saved_record(block, record, gridded, projection_types)

    def _source_record_labels(self, block: FormRepeatingGroupBlock) -> None:
        labels = [
            column.official_heading
            or (
                self.casilla_label(column.casilla_id)
                if (column.casilla_id is not None and column.casilla_id)
                else f"Columna {i}"
            )
            for i, column in enumerate(block.columns, 1)
        ]
        # A record can have dozens of fields. Preserve each heading in its own
        # row rather than joining them into an unreadable, oversized banner.
        for label in labels:
            self.line(label)

    def _source_record_rows(self, row_set: SheetRowSet) -> tuple[dict[int, str], dict[int, list[SheetValueCell]]]:
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
        return source_columns, rows

    def _matching_row_sets(self, block: FormRepeatingGroupBlock) -> list[SheetRowSet]:
        row_sets = [r for r in self.plan.row_sets if any(c.binding == block.binding_id for c in r.columns)]
        if len(row_sets) > 1:
            raise CalcSheetsEngineError("repeating form binding has ambiguous source row sets")
        return row_sets

    def _source_records(self, block: FormRepeatingGroupBlock) -> None:
        # Row sets expose binding identity, never an implicit positional join
        # to a differently shaped export record.
        row_sets = self._matching_row_sets(block)
        self._source_record_labels(block)
        if not row_sets:
            self.line("Sin registros aportados a esta vista. Consulte el detalle de origen.")
            return
        row_set = row_sets[0]
        source_columns, rows = self._source_record_rows(row_set)
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

    def repeating(self, block: FormRepeatingGroupBlock) -> None:
        """Render or initialize this form component."""
        known, saved_rows = self.records(block)
        projection_types = (
            {field.id: str(field.data_type) for field in resolve_form_projection_fields(self.registry_revision, block)}
            if any(column.export_field_id is not None for column in block.columns)
            else {}
        )
        if known:
            self._saved_records(block, saved_rows, projection_types)
        else:
            self._source_records(block)

    def _context_display(self, value: ModeloFormScalar) -> str | Decimal:
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
        return shown

    def _context_box(self, block: FormContextFieldBlock) -> int:
        value_column = 10 if (block.box_number is not None and block.box_number) else 9
        if block.box_number is not None and block.box_number:
            self.text(block.box_number, 9)
            self.span(9, 9, StyleRole.CASILLA, boxed=True)
        return value_column

    def context_field(self, block: FormContextFieldBlock) -> None:
        """Show only the explicitly declared immutable filing fact."""
        field = resolve_form_context_field(self.registry_revision, block)
        label = self.localized(block.heading_key) or block.official_heading or "Dato del formulario"
        self.text(label)
        value_column = self._context_box(block)
        if field.binding is not None:
            self.span(2, 8, StyleRole.FORM_LABEL)
            self.binding_value(field.binding, value_column, 12, readonly=True)
            self.heights.append(SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=32))
            self.row += 1
            return
        value = self.context(block)
        choice = form_context_choice(block, value)
        if choice is not None:
            value = self.localized(choice.heading_key) or choice.official_heading or "Opción"
        self.span(2, 8, StyleRole.FORM_LABEL)
        shown = self._context_display(value)
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
