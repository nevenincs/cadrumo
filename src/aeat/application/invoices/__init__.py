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

__all__ = [
    "InvoiceImportResult",
    "LinkInconsistency",
    "ReconciliationSuggestion",
    "find_invoice",
    "find_unmatched",
    "import_invoices_from_path",
    "link_transaction",
    "link_transaction_bidirectional",
    "merge_invoice_import",
    "parse_invoice_payload",
    "suggest_reconciliations",
    "verify_link_consistency",
]
