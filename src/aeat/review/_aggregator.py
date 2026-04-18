"""Cross-source review-queue aggregator.

Combines the five per-source adapters into one deterministically
sorted tuple of review items.
"""

from __future__ import annotations

from typing import cast

from ..config import Settings
from ._adapters import (
    divergences_pending,
    drafts_pending,
    inbox_pending,
    invoices_pending,
    transactions_pending,
)
from ._enums import ReviewItemKind, ReviewState, severity_rank
from ._models import ReviewItem


class ReviewQueue:
    """Static collector that aggregates pending review items across sources."""

    @staticmethod
    def collect(
        settings: Settings,
        *,
        kinds: frozenset[ReviewItemKind] | None = None,
        modelo: str | None = None,
        state: ReviewState = ReviewState.PENDING,
    ) -> tuple[ReviewItem, ...]:
        """Return every pending review item that matches the filters.

        Args:
            settings: Loaded :class:`aeat.config.Settings`.
            kinds: Optional set of :class:`ReviewItemKind` to include.
                ``None`` (default) means every kind. The argument is a
                ``frozenset`` so callers cannot mutate it after passing.
            modelo: Optional modelo filter. When set, items whose
                wrapped record has no modelo concept (inbox notifications
                without ``references_modelo``) are excluded.
            state: ``ReviewState.PENDING`` (default) or ``ReviewState.ALL``.
                ``ALL`` is reserved for a future "show resolved too"
                mode and currently returns the same set as ``PENDING``
                because every adapter only emits pending items today.

        Returns:
            A tuple sorted by ``(severity desc, since asc, item_id asc)``.
        """
        items: list[ReviewItem] = []
        # Each adapter returns a per-kind tuple; the discriminated
        # union keeps every member assignable to ReviewItem.
        items.extend(cast(list[ReviewItem], list(transactions_pending(settings))))
        items.extend(cast(list[ReviewItem], list(invoices_pending(settings))))
        items.extend(cast(list[ReviewItem], list(divergences_pending(settings))))
        items.extend(cast(list[ReviewItem], list(drafts_pending(settings))))
        items.extend(cast(list[ReviewItem], list(inbox_pending(settings))))

        if kinds is not None:
            items = [item for item in items if item.kind in kinds]
        if modelo is not None:
            items = [item for item in items if item.modelo == modelo]

        # state=ALL is currently identical to PENDING (no adapter emits
        # non-pending items yet); preserved as a forward-compatible flag.
        _ = state

        items.sort(key=lambda item: (-severity_rank(item.severity), item.since, item.item_id))
        return tuple(items)
