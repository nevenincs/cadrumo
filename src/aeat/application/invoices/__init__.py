"""Invoice orchestration surface.

Re-exports the application-level invoice service entry points from
:mod:`aeat.domain.invoices._service`. Callers outside the subpackage
must import only from this module so the private underscore-prefixed
implementation can evolve freely.

Key exports:

* :func:`find_invoice`, :func:`find_unmatched` — read paths against the
  invoice catalogue.
* :func:`link_transaction`, :func:`link_transaction_bidirectional` —
  link an invoice to one or more transactions.
* :func:`suggest_reconciliations` — heuristic matcher for unlinked
  invoices.
* :func:`verify_link_consistency` and :class:`LinkInconsistency` —
  audit helpers for cross-side link integrity.
"""

from __future__ import annotations

from ...domain.invoices._service import (
    LinkInconsistency,
    ReconciliationSuggestion,
    find_invoice,
    find_unmatched,
    link_transaction,
    link_transaction_bidirectional,
    suggest_reconciliations,
    verify_link_consistency,
)
from ._importing import (
    InvoiceImportResult,
    import_invoices_from_path,
    merge_invoice_import,
    parse_invoice_payload,
)
from ._projection import (
    InvoiceMatchProjection,
    InvoiceReviewProjection,
    apply_manual_invoice_match,
    invoice_display_amounts,
    invoice_review_status,
    project_invoice_payment_matches,
    project_invoice_review,
    project_invoice_reviews,
)
from ._reconciliation import (
    InvoiceReconciliationResult,
    ReconciliationSkippedSuggestion,
    reconcile_invoice_catalogues,
    reconcile_invoice_repositories,
)

__all__ = [
    "InvoiceImportResult",
    "InvoiceMatchProjection",
    "InvoiceReconciliationResult",
    "InvoiceReviewProjection",
    "LinkInconsistency",
    "ReconciliationSkippedSuggestion",
    "ReconciliationSuggestion",
    "apply_manual_invoice_match",
    "find_invoice",
    "find_unmatched",
    "import_invoices_from_path",
    "invoice_display_amounts",
    "invoice_review_status",
    "link_transaction",
    "link_transaction_bidirectional",
    "merge_invoice_import",
    "parse_invoice_payload",
    "project_invoice_payment_matches",
    "project_invoice_review",
    "project_invoice_reviews",
    "reconcile_invoice_catalogues",
    "reconcile_invoice_repositories",
    "suggest_reconciliations",
    "verify_link_consistency",
]
