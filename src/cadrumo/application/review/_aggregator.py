"""Cross-source review-queue aggregator.

Provides :class:`ReviewQueue`, which combines the per-source adapters
in :mod:`cadrumo.application.review._adapters` into one deterministically
sorted tuple of :class:`cadrumo.application.review.ReviewItem` values.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.config import Settings
from ...core.logging import get_logger
from ._adapters import (
    drafts_pending,
    invoices_pending,
    transactions_low_confidence,
    transactions_pending,
)
from .enums import ReviewItemKind, ReviewState, severity_rank
from .models import ReviewItem

_logger = get_logger(__name__)


class ReviewQueue:
    """Static collector that aggregates pending review items across sources.

    Combines the per-source adapters
    (:func:`transactions_pending`, :func:`invoices_pending`,
    :func:`drafts_pending`) into one deterministically sorted tuple.
    Severity is the primary sort key; ``since`` and ``item_id`` provide
    stable tiebreakers.
    """

    @staticmethod
    def collect(
        settings: Settings,
        *,
        bucket_id: str,
        kinds: frozenset[ReviewItemKind] | None = None,
        modelo: str | None = None,
        state: ReviewState = ReviewState.PENDING,
        confidence_below: Decimal | None = None,
    ) -> tuple[ReviewItem, ...]:
        """Return every pending review item that matches the filters.

        Args:
            settings: Loaded :class:`cadrumo.core.config.Settings`.
            bucket_id: Active bucket identifier used to scope the query
                to the correct operator profile.
            kinds: Optional set of :class:`ReviewItemKind` to include.
                ``None`` (default) means every kind. The argument is a
                ``frozenset`` so callers cannot mutate it after passing.
            modelo: Optional modelo filter. When set, items whose
                wrapped record has no modelo concept are excluded.
            state: ``ReviewState.PENDING`` (default) or
                ``ReviewState.ALL``. ``ALL`` returns the same set as
                ``PENDING`` while the adapters emit pending review
                items.
            confidence_below: Optional decision-confidence threshold.
                When set, the queue replaces the default
                transactions-pending source with
                :func:`transactions_low_confidence`: classified
                transactions whose ``classification_confidence`` is
                non-None and strictly less than the threshold. Other
                review kinds (invoices, findings) cannot
                satisfy a decision-confidence predicate and are
                excluded while this filter is active.

        Returns:
            A tuple sorted by ``(severity desc, since asc, item_id asc)``.
        """
        if confidence_below is not None:
            items: list[ReviewItem] = list(
                transactions_low_confidence(settings, bucket_id=bucket_id, threshold=confidence_below),
            )
        else:
            items = [
                *transactions_pending(settings, bucket_id=bucket_id),
                *invoices_pending(settings, bucket_id=bucket_id),
                *drafts_pending(settings, bucket_id=bucket_id),
            ]
        if kinds is not None:
            items = [item for item in items if item.kind in kinds]
        if modelo is not None:
            items = [item for item in items if item.modelo == modelo]
        items.sort(key=lambda item: (-severity_rank(item.severity), item.since, item.item_id))
        result = tuple(items)
        _logger.debug(
            "review queue collected items=%d kinds=%s modelo=%s",
            len(result),
            sorted(k.value for k in kinds) if kinds is not None else "all",
            modelo,
        )
        return result
