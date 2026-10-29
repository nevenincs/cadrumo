"""Grid and repeating-record rendering for form workbooks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from textwrap import wrap

from ....domain.calculations.registry.schema_form_layouts import (
    FormCell,
    FormCellKind,
    FormGridBlock,
    FormGridRow,
    FormRepeatingColumn,
)
from ...modelo.work_form_models import ModeloFormScalar
from .errors import CalcSheetsEngineError
from .form_scalar_builder import FormScalarBuilder
from .number_formats import numeric_format
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetRowHeight,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


class FormGridBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    FormScalarBuilder[M]
):
    """Render the corresponding declared form phase."""

    def _grid_header_height(self, row_heading: str, headings: list[str | None]) -> None:
        self.heights.append(
            SheetRowHeight(
                tab=TabName.FORM,
                row=self.row,
                height_pixels=min(
                    409, max(44, 18 * (1 + max(len(heading or "") for heading in [row_heading, *headings]) // 24))
                ),
            )
        )

    def _grid_header(self, block: FormGridBlock) -> None:
        headings = [self.localized(column.heading_key) or column.official_heading for column in block.columns]
        if any(not (heading is not None and heading) for heading in headings):
            raise CalcSheetsEngineError("form grid requires an authored column heading")
        row_heading = self.localized(block.row_heading_key) or block.official_row_heading or "Concepto"
        self.text(row_heading)
        self.span(2, 5, StyleRole.FORM_SECTION)
        for index, heading in enumerate(headings):
            start = 6 + index * 2
            self.text(heading, start)
            self.span(start, start + 1, StyleRole.FORM_SECTION)
        self._grid_header_height(row_heading, headings)
        self.row += 1

    def _grid_casilla(
        self, cell: FormCell, casilla_id: str, start: int, record_values: dict[str, ModeloFormScalar] | None
    ) -> ModeloFormScalar:
        visible_value: ModeloFormScalar = None
        self.text(self.placements[casilla_id].box_number or "", start)
        self.span(start, start, StyleRole.CASILLA, boxed=True)
        if record_values is None:
            self.value(casilla_id, start + 1, start + 1, constant=cell.literal, decimals=cell.literal_decimals)
            source = self.sources.get(casilla_id)
            if isinstance(source, SheetValueCell):
                visible_value = source.value
        else:
            self.record_value(casilla_id, record_values[casilla_id], start + 1, start + 1)
            visible_value = record_values[casilla_id]
        return visible_value

    def _grid_cell(
        self, cell: FormCell, start: int, record_values: dict[str, ModeloFormScalar] | None
    ) -> tuple[ModeloFormScalar, int]:
        visible_value: ModeloFormScalar = None
        text_width = sum(self.column_widths[start - 1 : start + 1]) - 2
        if cell.casilla_id is not None and cell.casilla_id:
            text_width = self.column_widths[start] - 2
            visible_value = self._grid_casilla(cell, cell.casilla_id, start, record_values)
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
        return visible_value, text_width

    def _grid_row(self, row: FormGridRow, record_values: dict[str, ModeloFormScalar] | None) -> None:
        heading = self.localized(row.heading_key) or row.official_heading
        if not (heading is not None and heading):
            raise CalcSheetsEngineError("form grid requires an authored row heading")
        self.text(heading)
        self.span(2, 5, StyleRole.FORM_LABEL)
        text_lines = sum(max(1, len(wrap(line, width=44))) for line in heading.splitlines())
        for column_index, cell in enumerate(row.cells):
            start = 6 + column_index * 2
            visible_value, text_width = self._grid_cell(cell, start, record_values)
            if isinstance(visible_value, str):
                text_lines = max(
                    text_lines,
                    sum(max(1, len(wrap(line, width=max(1, text_width)))) for line in visible_value.splitlines()),
                )
        self.heights.append(
            SheetRowHeight(tab=TabName.FORM, row=self.row, height_pixels=min(409, max(44, 18 * text_lines + 8)))
        )
        self.row += 1

    def grid(self, block: FormGridBlock, *, record_values: dict[str, ModeloFormScalar] | None = None) -> None:
        # A declared row is one row across every column. Splitting the columns
        # into vertical chunks severs the relationships in official tables.
        """Render or initialize this form component."""
        self._grid_header(block)
        for row in block.rows:
            self._grid_row(row, record_values)

    def _record_display(self, value: ModeloFormScalar) -> str | Decimal | bool:
        return (
            value.isoformat()
            if isinstance(value, date)
            else value
            if value is not None and (isinstance(value, bool) or not isinstance(value, int))
            else Decimal(value)
            if isinstance(value, int)
            else "Sin dato"
        )

    def record_value(
        self, casilla_id: str | None, value: ModeloFormScalar, column: int, end: int, *, data_type: str | None = None
    ) -> None:
        """Render a saved record value; scalar sources contribute formatting only."""
        self.text(self._record_display(value), column)
        self.span(column, end, StyleRole.FORM_COMPUTED, boxed=True)
        if isinstance(value, Decimal | int) and not isinstance(value, bool):
            casilla = self.casillas.get(casilla_id) if (casilla_id is not None and casilla_id) else None
            pattern = numeric_format(data_type or (casilla.data_type if casilla is not None else "decimal"))
            if pattern is not None:
                self.formats.append(
                    SheetNumberFormat(
                        address=SheetCellAddress.at(TabName.FORM, self.row, column),
                        data_type=pattern[0],
                        pattern=pattern[1],
                    )
                )

    def _record_label(self, column: FormRepeatingColumn) -> tuple[str, str | None]:
        label = (
            self.localized(column.heading_key)
            or column.official_heading
            or (
                self.casilla_label(column.casilla_id)
                if (column.casilla_id is not None and column.casilla_id)
                else "Dato del registro"
            )
        )
        box_number = (
            self.placements[column.casilla_id].box_number
            if (column.casilla_id is not None and column.casilla_id)
            else None
        )
        return label, box_number
