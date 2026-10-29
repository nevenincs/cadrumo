"""Project existing workbook cells into authored human presentation."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .errors import CalcSheetsEngineError
from .records import (
    SheetExportMetadata,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetRowSet,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .workbook_exclusions import formula_may_read_transport_cell


def _origin_label(tab: TabName, row: int, readonly: set[tuple[TabName, int]]) -> str:
    if (tab, row) in readonly:
        return "Dato de origen"
    return "Dato de entrada" if tab is TabName.ENTRADAS else "Cálculo"


def _calculation_label(
    cell: SheetValueCell,
    rows: dict[tuple[TabName, int], CasillaDefinition],
    readonly: set[tuple[TabName, int]],
    printed_boxes: dict[str, str | None],
    bindings: set[str],
    label: Callable[[str], str],
) -> Decimal | str | bool | None:
    address = cell.address
    value = cell.value
    if address.row == 1:
        return ("Origen", "Casilla", "Concepto", "Valor")[address.column - 1]
    if address.column == 1:
        return _origin_label(address.tab, address.row, readonly)
    if address.column == 2:
        owner = rows.get((address.tab, address.row))
        return (printed_boxes.get(owner.id, owner.form_number) or "") if owner else ""
    if address.column == 3 and isinstance(value, str) and value in bindings:
        return label(value)
    return value


def _tariff_label(cell: SheetValueCell, bindings: set[str], label: Callable[[str], str]) -> Decimal | str | bool | None:
    value = cell.value
    if cell.parameter is not None and cell.parameter:
        return label(cell.parameter)
    if isinstance(value, str) and value in bindings:
        return label(value)
    return {
        "Minimum base": "Base mínima",
        "Maximum base": "Base máxima",
        "Fixed quota": "Cuota fija",
        "Marginal rate": "Tipo marginal",
    }.get(str(value), value)


def _support_label(
    cell: SheetValueCell,
    rows: dict[tuple[TabName, int], CasillaDefinition],
    readonly: set[tuple[TabName, int]],
    printed_boxes: dict[str, str | None],
    bindings: set[str],
    label: Callable[[str], str],
) -> Decimal | str | bool | None:
    if cell.address.tab in (TabName.ENTRADAS, TabName.CALCULOS):
        return _calculation_label(cell, rows, readonly, printed_boxes, bindings, label)
    if cell.address.tab is TabName.TARIFFS:
        return _tariff_label(cell, bindings, label)
    return cell.value


def _discard_support_cell(cell: SheetValueCell, anchors: set[str]) -> bool:
    if (
        cell.address.tab not in (TabName.PROVENANCE, TabName.GUIDE, TabName.EVIDENCIA)
        and cell.address.qualified() not in anchors
    ):
        return False
    if cell.role not in ("label", "metadata"):
        raise CalcSheetsEngineError("human presentation cannot discard a data cell")
    return True


def project_existing_cells[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    revision: ModeloRevision,
    rows: dict[tuple[TabName, int], CasillaDefinition],
    excluded: frozenset[str],
    printed_boxes: dict[str, str | None],
    label: Callable[[str], str],
) -> list[SheetValueCell]:
    """Preserve data cells and replace authored labels on support tabs.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    readonly = {(c.address.tab, c.address.row) for c in plan.value_cells if c.role == "source_value"}
    anchors = {a.address.qualified() for a in plan.anchors}
    bindings = {b.id for b in revision.bindings}
    values: list[SheetValueCell] = []
    for cell in plan.value_cells:
        address = cell.address
        owner = rows.get((address.tab, address.row))
        if owner is not None and owner.id in excluded:
            continue
        if _discard_support_cell(cell, anchors):
            continue
        value = cell.value
        if cell.role == "label":
            value = _support_label(cell, rows, readonly, printed_boxes, bindings, label)
        values.append(cell.model_copy(update={"value": value}))
    return values


def human_rows[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M], casillas: dict[str, CasillaDefinition], excluded: frozenset[str]
) -> dict[tuple[TabName, int], CasillaDefinition]:
    """Resolve input and calculation rows and guard excluded formula references."""
    rows = {
        (c.address.tab, c.address.row): casillas[c.casilla_id]
        for c in (*plan.value_cells, *plan.formula_cells)
        if c.casilla_id in casillas and c.address.tab in (TabName.ENTRADAS, TabName.CALCULOS)
    }
    excluded_addresses = tuple(c.address for c in (*plan.value_cells, *plan.formula_cells) if c.casilla_id in excluded)
    if any(
        cell.casilla_id in excluded or formula_may_read_transport_cell(cell, excluded_addresses)
        for cell in plan.formula_cells
    ):
        raise CalcSheetsEngineError("workbook transport exclusion is referenced by a sheet formula")
    return rows


def human_row_sets(row_sets_in: tuple[SheetRowSet, ...], label: Callable[[str], str]) -> tuple[SheetRowSet, ...]:
    """Project row-set headers from authored labels."""
    row_sets = tuple(
        row_set.model_copy(
            update={
                "columns": tuple(
                    column.model_copy(update={"header_label": label(column.binding)}) for column in row_set.columns
                )
            }
        )
        for row_set in row_sets_in
    )
    return row_sets
