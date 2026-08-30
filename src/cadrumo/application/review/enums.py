"""Closed enumerations for the unified review queue.

Defines the kind, severity, and state taxonomy used by every
:class:`cadrumo.application.review.ReviewItem`. Reserved ``--kind`` tokens
are tracked in :data:`_RESERVED_KINDS` and surfaced to callers via
:func:`reserved_kind_reason`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ReviewItemKind(StrEnum):
    """Stable identifier for the source of a review item.

    The three members below cover every pending source emitted by the
    review queue. Additional parser tokens can be reserved without
    becoming emitted item kinds; reserved tokens are rejected with a
    ``ReviewKindReservedError`` that explains the accepted surface.
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


# Reserved kind tokens accepted for parsing but rejected by the CLI with
# a descriptive error.
_RESERVED_KINDS: Mapping[str, str] = MappingProxyType(
    {
        "classification": "classification decisions are not emitted review items",
        "approval-stale": ("represented by --kind finding when drafts emit ModeloDraftStatus.APROBACION_CADUCADA rows"),
    },
)


def reserved_kind_reason(token: str) -> str | None:
    """Return the blocking reason for a reserved token, or ``None``."""
    return _RESERVED_KINDS.get(token)
