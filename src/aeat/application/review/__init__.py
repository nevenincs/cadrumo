"""Unified review queue across the produce → verify → export pipeline.

Public surface — callers must import review enums, models, adapters,
and the aggregator exclusively from ``aeat.application.review`` and must not
reach into the private underscore modules inside this package. See
[[2026-04-18-unified-review-queue-adr]] for the architectural
contract.

The queue is read-only: every adapter loads from disk and emits a
typed :class:`ReviewItem` without mutating the source. New review
kinds land as additional adapters; existing adapters are not
re-touched (see ADR D7).
"""

from __future__ import annotations

from ._adapters import (
    divergences_pending,
    drafts_pending,
    invoices_pending,
    transactions_pending,
)
from ._aggregator import ReviewQueue
from ._enums import (
    ReviewFormat,
    ReviewItemKind,
    ReviewSeverity,
    ReviewState,
    reserved_kind_reason,
    severity_rank,
)
from ._errors import ReviewError, ReviewKindReservedError, ReviewSourceLoadError
from ._models import (
    DivergenceReviewItem,
    FindingReviewItem,
    InvoiceReviewItem,
    ReviewItem,
    TransactionReviewItem,
)

__all__ = [
    "DivergenceReviewItem",
    "FindingReviewItem",
    "InvoiceReviewItem",
    "ReviewError",
    "ReviewFormat",
    "ReviewItem",
    "ReviewItemKind",
    "ReviewKindReservedError",
    "ReviewQueue",
    "ReviewSeverity",
    "ReviewSourceLoadError",
    "ReviewState",
    "TransactionReviewItem",
    "divergences_pending",
    "drafts_pending",
    "invoices_pending",
    "reserved_kind_reason",
    "severity_rank",
    "transactions_pending",
]
