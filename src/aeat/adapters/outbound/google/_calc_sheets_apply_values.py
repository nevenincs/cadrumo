"""Google Sheets value-write payload builders for calc sheet exports."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from ....application.storage.calc_sheets import (
    SheetExportPlan,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
    evidence_table,
)


def _coerce_cell_value(value: Decimal | str | bool | None) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        # Sheets accepts plain floats; render the Decimal as a fixed
        # decimal string so very small/very large values do not round.
        return format(value, "f")
    return str(value)


def _build_value_data(value_cells: Iterable[SheetValueCell]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for cell in value_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[_coerce_cell_value(cell.value)]],
            },
        )
    return data


def _build_formula_data(formula_cells: Iterable[SheetFormulaCell]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for cell in formula_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[f"={cell.formula}"]],
            },
        )
    return data


def _build_row_set_header_data(row_sets: Iterable[SheetRowSet]) -> list[dict[str, Any]]:
    """Emit Detalle-tab header cells declaring each row-set column."""
    data: list[dict[str, Any]] = []
    for row_set in row_sets:
        for column in row_set.columns:
            data.append(
                {
                    "range": column.header_address.qualified(),
                    "values": [[column.header_label]],
                },
            )
    return data


def _build_evidence_value_data(plan: SheetExportPlan) -> list[dict[str, Any]]:
    """Build the Evidencia tab value writes, mirroring the offline workbook."""
    fingerprint, header, body = evidence_table(plan)
    tab = TabName.EVIDENCIA.value
    data: list[dict[str, Any]] = [
        {"range": f"'{tab}'!A1", "values": [["Snapshot fingerprint", fingerprint]]},
        {"range": f"'{tab}'!A3", "values": [list(header)]},
    ]
    for offset, row in enumerate(body):
        data.append({"range": f"'{tab}'!A{4 + offset}", "values": [list(row)]})
    return data


def _build_guide_value_data(plan: SheetExportPlan) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = [
        {"range": f"'{TabName.GUIDE.value}'!A1", "values": [[plan.guide.title]]},
    ]
    for index, paragraph in enumerate(plan.guide.paragraphs, start=3):
        data.append({"range": f"'{TabName.GUIDE.value}'!A{index}", "values": [[paragraph]]})
    metadata = plan.metadata
    base_row = 3 + len(plan.guide.paragraphs) + 2
    stamps = (
        ("Modelo", metadata.modelo_id),
        ("Revisión", metadata.revision_id),
        ("Período", f"{metadata.period} / {metadata.filing_year}"),
        ("Motor", metadata.engine_version),
        ("Registry SHA", metadata.registry_sha),
        ("Exportado", metadata.exported_at.isoformat()),
    )
    for offset, (label, value) in enumerate(stamps):
        data.append(
            {
                "range": f"'{TabName.GUIDE.value}'!A{base_row + offset}",
                "values": [[label, value]],
            },
        )
    return data
