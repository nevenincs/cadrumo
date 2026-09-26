"""Shared value tables consumed by every workbook materializer.

The tables are plan-derived content, not transport payloads: the online Google
Sheets adapter and the offline XLSX materializer render the same rows, and the
export identity stamps below are the same pairs whichever carrier holds them
(Sheets developer metadata online, workbook document properties offline).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

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
    """Return the value table written to the Evidencia sheet of every transport."""
    body = tuple(
        tuple(str(value) for value in _contributor_values(row)) for row in plan.evidence.contributor_rows
    ) + tuple(tuple(str(value) for value in _manual_values(row)) for row in plan.evidence.manual_entries)
    return (plan.evidence.snapshot_fingerprint or "", _EVIDENCE_HEADERS, body)


def guide_stamps(plan: SheetExportPlan) -> tuple[tuple[str, str], ...]:
    """Return the Guide sheet's operator-visible ``(label, value)`` export stamps."""
    metadata = plan.metadata
    return (
        ("Modelo", metadata.modelo_id),
        ("Revisión", metadata.revision_id),
        ("Período", f"{metadata.period.registry_token} / {metadata.filing_year}"),
        ("Motor", metadata.engine_version),
        ("Registry SHA", metadata.registry_sha),
        ("Exportado", metadata.exported_at.isoformat()),
    )


IDENTITY_STAMP_KEYS: Final[tuple[str, ...]] = (
    "cadrumo_engine_version",
    "cadrumo_registry_sha",
    "cadrumo_modelo_id",
    "cadrumo_revision_id",
    "cadrumo_filing_year",
    "cadrumo_period",
    "cadrumo_exported_at",
)
"""The keys carrying the workbook's registry and engine identity, in write order."""

RELATION_STAMP_PREFIX: Final[str] = "cadrumo_relation:"
"""Key prefix of one mirrored cross-revision relation's grounding stamp."""


def export_identity_stamps(plan: SheetExportPlan) -> tuple[tuple[str, str], ...]:
    """Return the machine-readable ``(key, value)`` stamps identifying one export.

    The registry and engine identity comes first, in :data:`IDENTITY_STAMP_KEYS`
    order, followed by one stamp per mirrored relation carrying its resolved
    value, provenance tier, source coordinates, and legal grounding. A relation
    field that is empty is omitted from its stamp rather than written as an empty
    assertion: absent grounding and blank grounding are different claims.

    Both transports stamp exactly these pairs -- online as spreadsheet developer
    metadata, offline as workbook custom document properties -- so a pull path
    validating compatibility reads the same identity whichever carrier produced
    the workbook.

    Args:
        plan: The export plan whose identity is being stamped.

    Returns:
        tuple[tuple[str, str], ...]: Key/value stamps in write order.
    """
    metadata = plan.metadata
    values = (
        metadata.engine_version,
        metadata.registry_sha,
        metadata.modelo_id,
        metadata.revision_id,
        str(metadata.filing_year),
        metadata.period.registry_token,
        metadata.exported_at.isoformat(),
    )
    stamps: list[tuple[str, str]] = list(zip(IDENTITY_STAMP_KEYS, values, strict=True))
    if plan.relation_provenance is None:
        return tuple(stamps)
    for relation in plan.relation_provenance.values:
        payload = {
            "value": str(relation.value) if relation.value is not None else "",
            "provenance": relation.provenance,
            "source_modelo": relation.source_modelo or "",
            "source_filing_year": str(relation.source_filing_year) if relation.source_filing_year is not None else "",
            "source_periods": "+".join(relation.source_periods),
            "source_casilla_ids": "+".join(relation.source_casilla_ids),
            "legal_refs": "+".join(relation.legal_refs),
            "source_refs": "+".join(relation.source_refs),
            "resolved_at": relation.resolved_at.isoformat() if relation.resolved_at is not None else "",
        }
        stamps.append(
            (
                f"{RELATION_STAMP_PREFIX}{relation.relation}",
                "; ".join(f"{key}={value}" for key, value in payload.items() if value),
            ),
        )
    return tuple(stamps)


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


__all__ = [
    "IDENTITY_STAMP_KEYS",
    "RELATION_STAMP_PREFIX",
    "evidence_table",
    "export_identity_stamps",
    "guide_stamps",
]
