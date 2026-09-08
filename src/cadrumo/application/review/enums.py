"""Closed enumerations for the unified review queue.

Defines the kind, severity, and state taxonomy used by every
:class:`cadrumo.application.review.ReviewItem`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ReviewItemKind(StrEnum):
    """Stable identifier for the source of a review item.

    The three members below cover every pending source emitted by the
    review queue.
    """

    TRANSACTION = "transaction"
    INVOICE = "invoice"
    FINDING = "finding"


class ReviewSeverity(StrEnum):
    """Editorial severity of a review item.

    Severity is derived per-source by the adapter, not stored on the
    underlying record. The ranking is fixed:
    CRITICAL > HIGH > NORMAL > INFO.
    """

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    INFO = "info"


_SEVERITY_RANK: Mapping[ReviewSeverity, int] = MappingProxyType(
    {
        ReviewSeverity.CRITICAL: 3,
        ReviewSeverity.HIGH: 2,
        ReviewSeverity.NORMAL: 1,
        ReviewSeverity.INFO: 0,
    },
)


def severity_rank(severity: ReviewSeverity) -> int:
    """Return the numeric rank of ``severity`` (CRITICAL=3 .. INFO=0)."""
    return _SEVERITY_RANK[severity]


class ReviewState(StrEnum):
    """Filter state for the review queue CLI.

    ``PENDING`` (default) returns only items that want the operator's
    attention. ``ALL`` uses the same adapter output while every review
    adapter emits pending items.
    """

    PENDING = "pending"
    ALL = "all"
