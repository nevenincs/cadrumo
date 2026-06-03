"""Offline XLSX materializer for ``SheetExportPlan`` records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING, Literal

from openpyxl import Workbook
from openpyxl.comments import Comment
from pydantic import BaseModel, Field

from ....core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._records import (
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
)

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet


_EVIDENCE_SIDECAR_SCHEMA_VERSION: Literal["calc-sheets-evidence-sidecar/v1"] = "calc-sheets-evidence-sidecar/v1"
_XLSX_MEDIA_TYPE: Literal["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_JSON_MEDIA_TYPE: Literal["application/json"] = "application/json"

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


class OfflineWorkbookEvidenceSidecar(BaseModel):
    """Machine-readable evidence sidecar emitted beside an offline workbook."""

    model_config = _STRICT_FROZEN

    schema_version: Literal["calc-sheets-evidence-sidecar/v1"] = _EVIDENCE_SIDECAR_SCHEMA_VERSION
    metadata: SheetExportMetadata
    workbook_sha256: str = Field(min_length=64, max_length=64)
    evidence: SheetEvidenceFacet


class OfflineWorkbookExportResult(BaseModel):
    """Serialized offline workbook plus its machine-readable evidence sidecar."""

    model_config = _STRICT_FROZEN

    workbook_payload: bytes
    workbook_media_type: Literal["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] = _XLSX_MEDIA_TYPE
    workbook_filename_extension: Literal["xlsx"] = "xlsx"
    workbook_sha256: str = Field(min_length=64, max_length=64)
    evidence_sidecar_payload: bytes
    evidence_sidecar_media_type: Literal["application/json"] = _JSON_MEDIA_TYPE
    evidence_sidecar_filename_extension: Literal["evidence.json"] = "evidence.json"
    evidence_sidecar_sha256: str = Field(min_length=64, max_length=64)


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


def build_evidence_sidecar(
    plan: SheetExportPlan,
    *,
    workbook_sha256: str,
) -> OfflineWorkbookEvidenceSidecar:
    """Build the machine-readable evidence sidecar for one workbook export."""
    return OfflineWorkbookEvidenceSidecar(
        metadata=plan.metadata,
        workbook_sha256=workbook_sha256,
        evidence=plan.evidence,
    )


def serialize_evidence_sidecar(sidecar: OfflineWorkbookEvidenceSidecar) -> bytes:
    """Serialize an evidence sidecar as canonical UTF-8 JSON bytes."""
    payload = sidecar.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8")


def serialize_offline_workbook(plan: SheetExportPlan) -> bytes:
    """Serialize an offline workbook plan to XLSX bytes."""
    workbook = build_offline_workbook(plan)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def serialize_offline_export(plan: SheetExportPlan) -> OfflineWorkbookExportResult:
    """Serialize an offline workbook and its adjacent evidence sidecar."""
    workbook_payload = serialize_offline_workbook(plan)
    workbook_sha256 = _sha256(workbook_payload)
    sidecar = build_evidence_sidecar(plan, workbook_sha256=workbook_sha256)
    evidence_sidecar_payload = serialize_evidence_sidecar(sidecar)
    return OfflineWorkbookExportResult(
        workbook_payload=workbook_payload,
        workbook_sha256=workbook_sha256,
        evidence_sidecar_payload=evidence_sidecar_payload,
        evidence_sidecar_sha256=_sha256(evidence_sidecar_payload),
    )


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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "OfflineWorkbookEvidenceSidecar",
    "OfflineWorkbookExportResult",
    "build_evidence_sidecar",
    "build_offline_workbook",
    "serialize_evidence_sidecar",
    "serialize_offline_export",
    "serialize_offline_workbook",
]
