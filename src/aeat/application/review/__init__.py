"""Unified review queue across the produce -> verify -> export pipeline.

Public surface — callers must import review enums, models, adapters,
and the aggregator exclusively from :mod:`aeat.application.review` and
must not reach into the private underscore modules inside this package.

The queue is read-only: every adapter loads from disk and emits a
typed :class:`ReviewItem` without mutating the source. Severity is
derived per-source by the adapter, not stored on the underlying record.
New review kinds land as additional adapters; existing adapters are
not re-touched.

Key exports:

* :class:`ReviewQueue` — cross-source aggregator.
* :class:`ReviewItem` — discriminated union over the three per-source
  shapes (:class:`TransactionReviewItem`, :class:`InvoiceReviewItem`,
  :class:`FindingReviewItem`).
* :class:`ReviewItemKind`, :class:`ReviewSeverity`, :class:`ReviewState`,
  :class:`ReviewFormat` — closed enumerations.
* :class:`ReviewError`, :class:`ReviewSourceLoadError`,
  :class:`ReviewKindReservedError` — error hierarchy.
"""

from __future__ import annotations

from ._actions import update_invoice_review, update_ledger_review
from ._adapters import (
    drafts_pending,
    invoices_pending,
    transactions_pending,
)
from ._aggregator import ReviewQueue
from ._edit import (
    EditClause,
    EditParseError,
    InvoiceEditKey,
    InvoiceEditSpec,
    LedgerEditKey,
    LedgerEditSpec,
    parse_edit_clause,
    parse_edit_clauses,
)
from ._enums import (
    ReviewFormat,
    ReviewItemKind,
    ReviewSeverity,
    ReviewState,
    reserved_kind_reason,
    severity_rank,
)
from ._errors import ReviewError, ReviewKindReservedError, ReviewSourceLoadError
from ._filter import (
    DeclaracionReviewFilterKey,
    DeclaracionReviewFilterSpec,
    DeclaracionReviewStatus,
    FilterClause,
    FilterParseError,
    InvoiceReviewFilterKey,
    InvoiceReviewFilterSpec,
    InvoiceReviewStatus,
    LedgerReviewFilterKey,
    LedgerReviewFilterSpec,
    LedgerReviewStatus,
    parse_filter_clause,
    parse_filter_clauses,
)
from ._models import (
    FindingReviewItem,
    InvoiceReviewItem,
    InvoiceReviewRecord,
    LedgerReviewRecord,
    ReviewItem,
    TransactionReviewItem,
)
from ._operator import (
    ACCEPTED_KINDS,
    ReviewQueueReport,
    ReviewQueueRow,
    project_review_item,
    project_review_queue,
)

__all__ = [
    "ACCEPTED_KINDS",
    "DeclaracionReviewFilterKey",
    "DeclaracionReviewFilterSpec",
    "DeclaracionReviewStatus",
    "EditClause",
    "EditParseError",
    "FilterClause",
    "FilterParseError",
    "FindingReviewItem",
    "InvoiceEditKey",
    "InvoiceEditSpec",
    "InvoiceReviewFilterKey",
    "InvoiceReviewFilterSpec",
    "InvoiceReviewItem",
    "InvoiceReviewRecord",
    "InvoiceReviewStatus",
    "LedgerEditKey",
    "LedgerEditSpec",
    "LedgerReviewFilterKey",
    "LedgerReviewFilterSpec",
    "LedgerReviewRecord",
    "LedgerReviewStatus",
    "ReviewError",
    "ReviewFormat",
    "ReviewItem",
    "ReviewItemKind",
    "ReviewKindReservedError",
    "ReviewQueue",
    "ReviewQueueReport",
    "ReviewQueueRow",
    "ReviewSeverity",
    "ReviewSourceLoadError",
    "ReviewState",
    "TransactionReviewItem",
    "drafts_pending",
    "invoices_pending",
    "parse_edit_clause",
    "parse_edit_clauses",
    "parse_filter_clause",
    "parse_filter_clauses",
    "project_review_item",
    "project_review_queue",
    "reserved_kind_reason",
    "severity_rank",
    "transactions_pending",
    "update_invoice_review",
    "update_ledger_review",
]
