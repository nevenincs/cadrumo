"""Offline XLSX materializer for ``SheetExportPlan`` records."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING

from openpyxl import Workbook
from openpyxl.comments import Comment

from ._records import (
    SheetEvidenceContributorRow,
    SheetEvidenceManualEntry,
    SheetExportPlan,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
)

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet


_EVIDENCE_HEADERS: tuple[str, ...] = (
    "Tipo",
    "Casilla",
    "Transaction ID",
    "Amount",
    "Currency",
    "Taxable base",
    "IVA rate",
    "IVA amount",
    "Counterparty",
    "Value",
    "Kind",
    "Note",
    "Attachment IDs",
    "Document link IDs",
    "Legal refs",
    "Source refs",
)


def build_offline_workbook(plan: SheetExportPlan) -> Workbook:
    """Materialise a ``SheetExportPlan`` as an offline openpyxl workbook."""
    workbook = Workbook()
    default = workbook.active
    default.title = TabName.ENTRADAS.value
    for tab in TabName:
        if tab.value not in workbook.sheetnames:
            workbook.create_sheet(tab.value)

    _write_value_cells(workbook, plan.value_cells)
    _write_formula_cells(workbook, plan.formula_cells)
    _write_row_set_headers(workbook, plan.row_sets)
    _write_guide(workbook[TabName.GUIDE.value], plan)
    _write_evidence(workbook[TabName.EVIDENCIA.value], plan)
    return workbook


def serialize_offline_workbook(plan: SheetExportPlan) -> bytes:
    """Serialize an offline workbook plan to XLSX bytes."""
    workbook = build_offline_workbook(plan)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_value_cells(workbook: Workbook, cells: Iterable[SheetValueCell]) -> None:
    for cell in cells:
        worksheet = workbook[cell.address.tab.value]
        target = worksheet.cell(row=cell.address.row, column=cell.address.column)
        target.value = _coerce_cell_value(cell.value)
        if cell.note is not None:
            target.comment = Comment(cell.note, "AEAT")


def _write_formula_cells(workbook: Workbook, cells: Iterable[SheetFormulaCell]) -> None:
    for cell in cells:
        worksheet = workbook[cell.address.tab.value]
        worksheet.cell(row=cell.address.row, column=cell.address.column).value = f"={cell.formula}"


def _write_row_set_headers(workbook: Workbook, row_sets: Iterable[SheetRowSet]) -> None:
    for row_set in row_sets:
        worksheet = workbook[row_set.tab.value]
        for column in row_set.columns:
            worksheet.cell(
                row=column.header_address.row,
                column=column.header_address.column,
            ).value = column.header_label


def _write_guide(worksheet: Worksheet, plan: SheetExportPlan) -> None:
    worksheet["A1"] = plan.guide.title
    for row, paragraph in enumerate(plan.guide.paragraphs, start=3):
        worksheet.cell(row=row, column=1).value = paragraph

    metadata = plan.metadata
    base_row = 3 + len(plan.guide.paragraphs) + 2
    stamps = (
        ("Modelo", metadata.modelo_id),
        ("Revision", metadata.revision_id),
        ("Periodo", f"{metadata.period} / {metadata.filing_year}"),
        ("Motor", metadata.engine_version),
        ("Registry SHA", metadata.registry_sha),
        ("Exportado", metadata.exported_at.isoformat()),
    )
    for offset, (label, value) in enumerate(stamps):
        worksheet.cell(row=base_row + offset, column=1).value = label
        worksheet.cell(row=base_row + offset, column=2).value = value


def _write_evidence(worksheet: Worksheet, plan: SheetExportPlan) -> None:
    worksheet["A1"] = "Snapshot fingerprint"
    worksheet["B1"] = plan.evidence.snapshot_fingerprint or ""
    for column, header in enumerate(_EVIDENCE_HEADERS, start=1):
        worksheet.cell(row=3, column=column).value = header

    row_index = 4
    for row in plan.evidence.contributor_rows:
        _write_evidence_row(worksheet, row_index, _contributor_values(row))
        row_index += 1
    for row in plan.evidence.manual_entries:
        _write_evidence_row(worksheet, row_index, _manual_values(row))
        row_index += 1

    worksheet.freeze_panes = "A4"
    worksheet.protection.sheet = True


def _write_evidence_row(worksheet: Worksheet, row_index: int, values: Sequence[object]) -> None:
    for column, value in enumerate(values, start=1):
        worksheet.cell(row=row_index, column=column).value = value


def _contributor_values(row: SheetEvidenceContributorRow) -> tuple[object, ...]:
    return (
        "ledger",
        row.casilla_id,
        row.transaction_id,
        _format_decimal(row.amount),
        row.currency,
        _format_optional_decimal(row.taxable_base),
        _format_optional_decimal(row.iva_rate),
        _format_optional_decimal(row.iva_amount),
        row.counterparty or "",
        "",
        "",
        "",
        _join(row.attachment_ids),
        _join(row.document_link_ids),
        _join(row.legal_refs),
        _join(row.source_refs),
    )


def _manual_values(row: SheetEvidenceManualEntry) -> tuple[object, ...]:
    return (
        "manual",
        row.casilla_id,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        row.value,
        row.kind,
        row.note,
        "",
        "",
        _join(row.legal_refs),
        _join(row.source_refs),
    )


def _coerce_cell_value(value: Decimal | str | bool | None) -> object:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return _format_decimal(value)
    return value


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


def _format_optional_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return _format_decimal(value)


def _join(values: tuple[str, ...]) -> str:
    return ";".join(values)


__all__ = [
    "build_offline_workbook",
    "serialize_offline_workbook",
]
