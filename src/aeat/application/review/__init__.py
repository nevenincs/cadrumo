"""Application facade for the read-only operator review queue.

Callers import review enums, models, adapters, and projections exclusively from
:mod:`aeat.application.review`; private underscore modules remain implementation
details. The canonical CLI surface is ``aeat app review queue`` and ``show``.
Those commands are read-only: queue adapters load bucket-scoped source records,
derive severity, and emit typed rows without mutating ledger, invoice, filing, or
modelo state.

Internally, :class:`ReviewQueue` aggregates the three concrete
:class:`ReviewItem` variants:
:class:`TransactionReviewItem`, :class:`InvoiceReviewItem`, and
:class:`FindingReviewItem`. The operator-facing projection layer maps those
internal kinds into :class:`ReviewQueueRow` values using the accepted
``--kind`` / ``--source-kind`` vocabulary exposed by :data:`ACCEPTED_KINDS`:
``ledger_transaction``, ``purchase_invoice_evidence``, ``payable_invoice``,
``collectible_invoice``, and ``modelo_finding``. ``live_notification`` and
``sync_divergence`` remain reserved vocabulary until concrete review sources are
wired.

The exported :func:`update_ledger_review` and :func:`update_invoice_review`
helpers append workflow-attention history only. Durable ledger facts, invoice
facts, filing findings, and bucket events stay owned by their source
application surfaces.

See Also:
    :class:`ReviewQueue`
        Cross-source aggregator over read-only adapters.
    :class:`ReviewQueueReport`
        Application report consumed by the CLI review renderer.
    :class:`ReviewQueueRow`
        Operator-facing queue row with owner surface and next command metadata.
    :class:`ReviewItem`
        Internal discriminated union emitted by source adapters.
    :class:`ReviewItemKind`
        Internal adapter-kind enum, distinct from accepted operator kind strings.
    :data:`ACCEPTED_KINDS`
        Accepted operator ``--kind`` values after source-kind projection.
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
