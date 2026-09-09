"""Shared value tables consumed by the live Google Sheets materializer."""

from __future__ import annotations

from decimal import Decimal

from ....core.decimal.formatting import format_decimal
from .records import SheetEvidenceContributorRow, SheetEvidenceManualEntry, SheetExportPlan

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


def evidence_table(plan: SheetExportPlan) -> tuple[str, tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Return the value table written to the live Evidencia sheet."""
    body = tuple(
        tuple(str(value) for value in _contributor_values(row)) for row in plan.evidence.contributor_rows
    ) + tuple(tuple(str(value) for value in _manual_values(row)) for row in plan.evidence.manual_entries)
    return (plan.evidence.snapshot_fingerprint or "", _EVIDENCE_HEADERS, body)


def guide_stamps(plan: SheetExportPlan) -> tuple[tuple[str, str], ...]:
    """Return the live Guide sheet's ``(label, value)`` export stamps."""
    metadata = plan.metadata
    return (
        ("Modelo", metadata.modelo_id),
        ("Revisión", metadata.revision_id),
        ("Período", f"{metadata.period.registry_token} / {metadata.filing_year}"),
        ("Motor", metadata.engine_version),
        ("Registry SHA", metadata.registry_sha),
        ("Exportado", metadata.exported_at.isoformat()),
    )


def _contributor_values(row: SheetEvidenceContributorRow) -> tuple[str, ...]:
    return (
        "ledger",
        row.casilla_id,
        row.transaction_id,
        format_decimal(row.amount),
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


def _manual_values(row: SheetEvidenceManualEntry) -> tuple[str, ...]:
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


def _format_optional_decimal(value: Decimal | None) -> str:
    return format_decimal(value, none_value="")


def _join(values: tuple[str, ...]) -> str:
    return ";".join(values)


__all__ = ["evidence_table", "guide_stamps"]
