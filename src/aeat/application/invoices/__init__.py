"""Application invoice orchestration and calculation-source surface.

This package is the public application boundary for invoice catalogue import,
linking, review, reconciliation, and source-mesh projection. Callers outside the
subpackage must import only from this module so private underscore-prefixed
implementation modules can evolve freely.

The calculation-facing export is :class:`InvoiceCatalogueSourceResolver`. It
projects both rich :class:`~aeat.domain.invoices.InvoiceCatalogue` entries and
slim :class:`~aeat.application.ledger.BusinessOperationInvoice` records into
:class:`~aeat.application.aggregation.CalculationSourceResolution` values for
the :attr:`~aeat.core.BindingSourceKind.COLLECTIBLE_INVOICE` and
:attr:`~aeat.core.BindingSourceKind.PAYABLE_INVOICE` source kinds. The helper
:func:`invoice_direction_to_source_kind` is the single direction-to-settlement
mapping shared with the operator ``aeat app ledger invoice`` surface.

Key exports:

* :func:`find_invoice`, :func:`find_unmatched` — read paths against the
  invoice catalogue.
* :func:`link_transaction` — link an invoice to one or more transactions.
* :func:`link_invoice_transaction_repositories` — persisted
  bidirectional invoice/transaction linking.
* :func:`suggest_reconciliations` — heuristic matcher for unlinked
  invoices.
* :func:`verify_link_consistency` and :class:`LinkInconsistency` —
  audit helpers for cross-side link integrity.
* :class:`InvoiceCatalogueSourceResolver` — the live calculate-path resolver for
  invoice-source bindings and Modelo 349 detail rows.
"""

from __future__ import annotations

from ...domain.invoices._service import (
    find_invoice,
    find_unmatched,
    link_transaction,
    suggest_reconciliations,
    verify_link_consistency,
)
from ._creation import (
    CatalogueInvoiceCreateResult,
    build_catalogue_invoice,
    create_catalogue_invoice,
)
from ._importing import (
    InvoiceImportResult,
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

__all__ = [
    "CatalogueInvoiceCreateResult",
    "CatalogueInvoiceRemoveResult",
    "InvoiceCatalogueSourceResolver",
    "InvoiceImportResult",
    "InvoiceListRow",
    "InvoiceMatchProjection",
    "InvoiceMatchRow",
    "InvoiceReconciliationResult",
    "InvoiceReviewProjection",
    "InvoiceTransactionLinkResult",
    "ReconciliationSkippedSuggestion",
    "apply_manual_invoice_match",
    "build_catalogue_invoice",
    "create_catalogue_invoice",
    "find_invoice",
    "find_unmatched",
    "get_invoice_from_repository",
    "import_invoices_from_path",
    "invoice_direction_to_source_kind",
    "invoice_display_amounts",
    "invoice_review_status",
    "link_invoice_transaction_catalogues",
    "link_invoice_transaction_repositories",
    "link_transaction",
    "list_invoice_repository_rows",
    "list_invoice_rows",
    "list_unmatched_invoice_repository_rows",
    "list_unmatched_invoice_rows",
    "merge_invoice_import",
    "parse_invoice_payload",
    "project_invoice_payment_matches",
    "project_invoice_review",
    "project_invoice_reviews",
    "reconcile_invoice_catalogues",
    "reconcile_invoice_repositories",
    "remove_catalogue_invoice",
    "resolve_catalogue_invoice",
    "resolve_catalogue_invoice_from_repository",
    "suggest_reconciliations",
    "verify_invoice_repository_links",
    "verify_link_consistency",
]
