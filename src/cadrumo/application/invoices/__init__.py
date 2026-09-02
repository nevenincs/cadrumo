"""Inert namespace for the application invoice orchestration package.

This package exports nothing. Every contract below has one canonical defining
module, and callers -- inside the package and out -- import it from there.

Where the contracts live:

- Catalogue writes -- ``catalogue_creation`` for ``build_catalogue_invoice`` and
  ``create_catalogue_invoice``, ``catalogue_lifecycle`` for the patch, update and
  remove paths, and ``bulk_import`` for the spreadsheet ingestion surface and its
  column contracts.
- Catalogue reads -- ``catalogue_reads``, holding the row projections and the
  repository-backed link verification.
- Operator entry -- ``creation_wizard`` for the guided create path and its field
  errors.
- Calculation-facing surface -- ``source_resolver``, defining
  :class:`InvoiceCatalogueSourceResolver` and the single
  ``invoice_direction_to_source_kind`` mapping shared with the
  ``aeat app ledger invoice`` operator surface.
- Linking -- ``transaction_linking`` for the bidirectional invoice/transaction
  links. The private ``_projection`` module has no consumer outside this
  package.
- Tax-position helpers -- ``issuer_establishment`` and ``self_counterparty``.

``domain.invoices`` remains the sole canonical source for ``find_invoice``,
``find_unmatched``, ``link_transaction``, ``suggest_reconciliations`` and
``verify_link_consistency``; this package never re-exported the last three and
now re-exports nothing at all.

See Also:
    :mod:`domain.invoices`
        Invoice catalogue, line arithmetic, payment state, and the
        reconciliation/link authority this package orchestrates.
    :mod:`application.ledger`
        Payable/collectible invoice CRUD and ledger evidence links that
        converge with catalogue data at source resolution.
    :mod:`application.aggregation`
        Source-mesh envelope receiving invoice binding values, diagnostics,
        detail rows and provenance.
    :mod:`domain.calculations.registry`
        Binding declarations and invoice observation contracts consumed by
        modelo calculation.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
