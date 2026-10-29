"""Source cells and declared geometry for form workbook rendering."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ....domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormGridBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...export.review_form_data import ReviewSavedForm
from ...modelo.work_form_models import ModeloFormScalar
from .errors import CalcSheetsEngineError
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)


def form_sources[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    casillas: dict[str, CasillaDefinition],
    saved_form: ReviewSavedForm | None,
    saved_value: Callable[[ModeloFormScalar], str | Decimal | bool | None],
) -> dict[str, SheetValueCell | SheetFormulaCell]:
    """Resolve source cells and refuse ambiguous casilla values."""
    sources: dict[str, SheetValueCell | SheetFormulaCell] = {}
    for cell in (*plan.value_cells, *plan.formula_cells):
        if cell.casilla_id is not None and cell.address.tab in (TabName.ENTRADAS, TabName.CALCULOS):
            if cell.casilla_id in sources:
                raise CalcSheetsEngineError("form source contains ambiguous duplicate casilla values")
            sources[cell.casilla_id] = cell
    if saved_form is not None:
        return {
            item.id: SheetValueCell(
                address=SheetCellAddress.at(TabName.CALCULOS, index, 4),
                value=saved_value(item.value),
                casilla_id=item.id,
                role="source_value",
            )
            for index, item in enumerate(saved_form.scalars, 1)
            if item.id in casillas
        }
    return sources


def _grids(block: FormBlockDefinition) -> tuple[FormGridBlock, ...]:
    if isinstance(block, FormGridBlock):
        return (block,)
    if isinstance(block, FormRepeatingGroupBlock):
        return block.grids
    return ()


def form_column_widths(layout: FormLayoutDefinition) -> tuple[int, ...]:
    """Choose form widths from the widest declared grid."""
    widest_grid = max(
        (
            len(grid.columns)
            for page in layout.pages
            for section in page.sections
            for block in section.blocks
            for grid in _grids(block)
        ),
        default=0,
    )
    return (
        (3, 12, 12, 12, 12, *(width for _ in range(widest_grid) for width in (9, 18)), 3)
        if widest_grid > 3
        else (3, 12, 12, 12, 12, 12, 18, 12, 18, 10, 18, 10, 3)
        if widest_grid
        else (3, 12, 12, 12, 12, 12, 12, 12, 7, 10, 10, 10, 3)
    )
