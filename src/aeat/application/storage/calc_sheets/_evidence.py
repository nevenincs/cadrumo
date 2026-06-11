"""Evidence adapters for calc-sheets workbook export plans."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ....domain.modelos._ledger_filing_snapshot import LedgerFilingEvidence
from ._errors import CalcSheetsEngineError
from ._records import SheetEvidenceContributorRow, SheetEvidenceFacet, SheetEvidenceManualEntry


def sheet_evidence_from_ledger_filing(
    evidence: LedgerFilingEvidence,
    *,
    contributor_casillas: Mapping[str, Iterable[str]],
) -> SheetEvidenceFacet:
    """Project bundled filing evidence into the per-casilla workbook facet.

    ``LedgerFilingEvidence`` is contributor-oriented; the workbook evidence
    surface is casilla-oriented. The caller must therefore provide the
    generic attribution map from each contributor transaction id to the
    casilla ids it supports. Missing attribution is refused instead of being
    guessed from modelo-specific tax facts.

    Returns:
        :class:`SheetEvidenceFacet`: The projected evidence facet.
    """
    contributor_rows: list[SheetEvidenceContributorRow] = []
    for row in evidence.rows:
        casillas = tuple(str(casilla).strip() for casilla in contributor_casillas.get(row.transaction_id, ()))
        casillas = tuple(casilla for casilla in casillas if casilla)
        if not casillas:
            raise CalcSheetsEngineError(
                f"ledger filing evidence contributor {row.transaction_id!r} has no workbook casilla attribution",
            )
        for casilla_id in casillas:
            contributor_rows.append(
                SheetEvidenceContributorRow(
                    casilla_id=casilla_id,
                    transaction_id=row.transaction_id,
                    amount=row.amount,
                    currency=row.currency,
                    taxable_base=row.taxable_base,
                    iva_rate=row.iva_rate,
                    iva_amount=row.iva_amount,
                    counterparty=row.counterparty,
                    attachment_ids=row.attachment_ids,
                    document_link_ids=row.document_link_ids,
                    legal_refs=row.legal_refs,
                    source_refs=row.source_refs,
                ),
            )

    manual_entries = tuple(
        SheetEvidenceManualEntry(
            casilla_id=entry.casilla,
            value=entry.value,
            kind=entry.kind,
            note=entry.note,
        )
        for entry in evidence.manual_entries
    )
    return SheetEvidenceFacet(
        snapshot_fingerprint=evidence.snapshot_fingerprint,
        contributor_rows=tuple(contributor_rows),
        manual_entries=manual_entries,
    )


__all__ = ["sheet_evidence_from_ledger_filing"]
