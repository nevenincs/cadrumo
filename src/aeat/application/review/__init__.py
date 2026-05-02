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
* :class:`ReviewItem` — discriminated union over the four per-source
  shapes (:class:`TransactionReviewItem`, :class:`InvoiceReviewItem`,
  :class:`DivergenceReviewItem`, :class:`FindingReviewItem`).
* :class:`ReviewItemKind`, :class:`ReviewSeverity`, :class:`ReviewState`,
  :class:`ReviewFormat` — closed enumerations.
* :class:`ReviewError`, :class:`ReviewSourceLoadError`,
  :class:`ReviewKindReservedError` — error hierarchy.
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
