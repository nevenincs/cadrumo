"""Evidence adapters for calc-sheets workbook export plans.

:func:`sheet_evidence_from_ledger_filing` projects
:class:`LedgerFilingEvidence` into a :class:`SheetEvidenceFacet` made of
:class:`SheetEvidenceContributorRow` and :class:`SheetEvidenceManualEntry`
records for the workbook evidence surface.

The adapter is deliberately attribution-driven. Ledger evidence names the
contributing transactions and manual facts; the caller supplies the mapping from
each contributor to the canonical :class:`CasillaId` values it supports so this
module never guesses modelo-specific tax meaning from row contents.

See Also:
    :class:`cadrumo.domain.modelos.ledger_filing_snapshot.LedgerFilingEvidence`
        Bundled fact basis attached to a ledger-derived calculation revision.
    :class:`SheetEvidenceFacet`
        Workbook-plan evidence facet rendered into the Evidencia tab and JSON
        sidecar.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ....core.casilla_id import CasillaId
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence
from ._records import SheetEvidenceContributorRow, SheetEvidenceFacet, SheetEvidenceManualEntry
from .errors import CalcSheetsEngineError


def sheet_evidence_from_ledger_filing(
    evidence: LedgerFilingEvidence,
    *,
    casilla_ids_by_contributor_id: Mapping[str, Iterable[CasillaId]],
) -> SheetEvidenceFacet:
    """Project bundled filing evidence into the per-casilla workbook facet.

    :class:`LedgerFilingEvidence` is contributor-oriented; the workbook evidence
    surface is casilla-oriented. The caller must therefore provide the
    generic attribution map from each contributor transaction id to the
    canonical :class:`CasillaId` values it supports. Missing attribution raises
    :class:`CalcSheetsEngineError` instead of being guessed from modelo-specific
    tax facts.

    Returns:
        :class:`SheetEvidenceFacet`: The projected evidence facet.
    """
    contributor_rows: list[SheetEvidenceContributorRow] = []
    for row in evidence.rows:
        contributor_casilla_ids = tuple(casilla_ids_by_contributor_id.get(row.transaction_id, ()))
        if not contributor_casilla_ids:
            raise CalcSheetsEngineError(
                translated_message="errors.error.error_calc_sheets_engine",
                context={
                    "transaction_id": str(row.transaction_id),
                    "workbook_casilla_attribution_present": False,
                },
            )
        for casilla_id in contributor_casilla_ids:
            contributor_rows.append(
                SheetEvidenceContributorRow(
                    casilla_id=casilla_id,
                    transaction_id=row.transaction_id,
                    amount=row.amount,
                    currency=row.currency,
                    fx_rate=row.fx_rate,
                    value_in_eur=row.value_in_eur,
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
            casilla_id=entry.casilla_id,
            value=entry.value,
            kind=entry.kind,
            note=entry.note,
            legal_refs=entry.legal_refs,
            source_refs=entry.source_refs,
        )
        for entry in evidence.manual_entries
    )
    return SheetEvidenceFacet(
        snapshot_fingerprint=evidence.snapshot_fingerprint,
        contributor_rows=tuple(contributor_rows),
        manual_entries=manual_entries,
    )


__all__ = ["sheet_evidence_from_ledger_filing"]
