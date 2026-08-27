"""Closed outcome taxonomy for non-authenticating profile discovery.

Listing profiles is a pure read: it recognises committed capsules and reports
their identity and label, and it never unlocks, authenticates, repairs, or
publishes anything.  A read that pure still has three distinguishable endings,
and collapsing them loses the one fact an operator acts on -- whether to retry,
to repair the store, or to believe an empty list.
"""

from __future__ import annotations

from enum import StrEnum


class ProfileSummaryOutcome(StrEnum):
    """How one anchored profile-summary observation ended."""

    RECOGNIZED = "recognized"
    """Every current capsule was observed coherently within one anchor."""

    CONCURRENT_CHANGE = "concurrent_change"
    """A capsule changed generation mid-observation; the listing is retryable."""

    DEGRADED = "degraded"
    """A current capsule is malformed or unreadable; the store needs attention."""


__all__ = ["ProfileSummaryOutcome"]
