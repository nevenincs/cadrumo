"""Application invoice orchestration and calculation-source surface.

This package is the public application boundary for invoice catalogue import,
linking, review, reconciliation, and source-mesh projection. Callers outside the
subpackage must import only from this module so private underscore-prefixed
implementation modules can evolve freely.

The calculation-facing export is :class:`InvoiceCatalogueSourceResolver`. It
projects both rich :class:`domain.invoices.InvoiceCatalogue` entries and
slim :class:`application.ledger.BusinessOperationInvoice` records into
:class:`application.aggregation.CalculationSourceResolution` values for
the :attr:`core.BindingSourceKind.COLLECTIBLE_INVOICE` and
:attr:`core.BindingSourceKind.PAYABLE_INVOICE` source kinds. The helper
:func:`invoice_direction_to_source_kind` is the single direction-to-settlement
mapping shared with the operator ``aeat app ledger invoice`` surface.

Key exports:

* :func:`find_invoice`, :func:`find_unmatched` — read paths against the
  invoice catalogue.
* :func:`link_invoice_transaction_repositories` — persisted
  bidirectional invoice/transaction linking.
* :class:`LinkInconsistency` — audit result for cross-side link integrity.
* :class:`InvoiceCatalogueSourceResolver` — the live calculate-path resolver for
  invoice-source bindings and Modelo 349 detail rows.

:func:`domain.invoices.link_transaction`,
:func:`domain.invoices.suggest_reconciliations`, and
:func:`domain.invoices.verify_link_consistency` are NOT re-exported here;
:mod:`domain.invoices` is their sole canonical source.

See Also:
    :mod:`domain.invoices`
        Rich invoice catalogue, line arithmetic, payment state, and
        reconciliation/link authority adapted by this application facade.
    :mod:`application.ledger`
        Slim payable/collectible invoice CRUD and ledger transaction evidence
        links that converge with invoice catalogue data at source resolution.
    :mod:`domain.transactions`
        Transaction catalogue whose ids are linked from invoices and reported
        as calculation source provenance.
    :mod:`application.aggregation`
        Source-mesh envelope receiving invoice binding values, diagnostics,
        detail rows, and provenance.
    :mod:`domain.calculations.registry`
        Pure binding declarations and invoice observation contracts consumed by
        modelo calculation.
"""

from __future__ import annotations

from ...domain.invoices import find_invoice, find_unmatched
from ._bulk_import import (
    BULK_INVOICE_IMPORT_ALLOWED_COLUMNS,
    BULK_INVOICE_IMPORT_REQUIRED_COLUMNS,
    BulkInvoiceImportResult,
    BulkInvoiceImportRow,
    BulkInvoiceImportRowFailure,
    import_invoices_from_rows,
    read_bulk_invoice_import_rows,
)
from ._creation import (
    CatalogueInvoiceCreateResult,
    build_catalogue_invoice,
    create_catalogue_invoice,
    numeric_iva_rate_slots,
)
from ._importing import (
    InvoiceImportResult,
    InvoiceRowPayload,
    import_invoices_from_path,
    merge_invoice_import,
    parse_invoice_payload,
)
from ._lifecycle import (
    CatalogueInvoiceRemoveResult,
    remove_catalogue_invoice,
    resolve_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
)
from ._linking import (
    InvoiceTransactionLinkResult,
    link_invoice_transaction_catalogues,
    link_invoice_transaction_repositories,
)
from ._projection import (
    InvoiceMatchProjection,
    InvoiceMatchRow,
    InvoiceReviewProjection,
    apply_manual_invoice_match,
    invoice_display_amounts,
    invoice_review_status,
    project_invoice_payment_matches,
    project_invoice_review,
    project_invoice_reviews,
)
from ._queries import (
    InvoiceListRow,
    get_invoice_from_repository,
    list_invoice_repository_rows,
    list_invoice_rows,
    list_unmatched_invoice_repository_rows,
    list_unmatched_invoice_rows,
    verify_invoice_repository_links,
)
from ._reconciliation import (
    InvoiceReconciliationResult,
    ReconciliationSkippedSuggestion,
    reconcile_invoice_catalogues,
    reconcile_invoice_repositories,
)
from ._source_resolver import InvoiceCatalogueSourceResolver, invoice_direction_to_source_kind
from ._wizard import InvoiceWizardFieldError, InvoiceWizardResult, create_invoice_via_wizard

__all__ = [
    "BULK_INVOICE_IMPORT_ALLOWED_COLUMNS",
    "BULK_INVOICE_IMPORT_REQUIRED_COLUMNS",
    "BulkInvoiceImportResult",
    "BulkInvoiceImportRow",
    "BulkInvoiceImportRowFailure",
    "CatalogueInvoiceCreateResult",
    "CatalogueInvoiceRemoveResult",
    "InvoiceCatalogueSourceResolver",
    "InvoiceImportResult",
    "InvoiceListRow",
    "InvoiceMatchProjection",
    "InvoiceMatchRow",
    "InvoiceReconciliationResult",
    "InvoiceReviewProjection",
    "InvoiceRowPayload",
    "InvoiceTransactionLinkResult",
    "InvoiceWizardFieldError",
    "InvoiceWizardResult",
    "ReconciliationSkippedSuggestion",
    "apply_manual_invoice_match",
    "build_catalogue_invoice",
    "create_catalogue_invoice",
    "create_invoice_via_wizard",
    "find_invoice",
    "find_unmatched",
    "get_invoice_from_repository",
    "import_invoices_from_path",
    "import_invoices_from_rows",
    "invoice_direction_to_source_kind",
    "invoice_display_amounts",
    "invoice_review_status",
    "link_invoice_transaction_catalogues",
    "link_invoice_transaction_repositories",
    "list_invoice_repository_rows",
    "list_invoice_rows",
    "list_unmatched_invoice_repository_rows",
    "list_unmatched_invoice_rows",
    "merge_invoice_import",
    "numeric_iva_rate_slots",
    "parse_invoice_payload",
    "project_invoice_payment_matches",
    "project_invoice_review",
    "project_invoice_reviews",
    "read_bulk_invoice_import_rows",
    "reconcile_invoice_catalogues",
    "reconcile_invoice_repositories",
    "remove_catalogue_invoice",
    "resolve_catalogue_invoice",
    "resolve_catalogue_invoice_from_repository",
    "verify_invoice_repository_links",
]
