"""Closed enumerations for the unified review queue.

Defines the kind, severity, and state taxonomy used by every
:class:`aeat.application.review.ReviewItem`. Reserved-but-unimplemented
``--kind`` tokens are tracked in :data:`_RESERVED_KINDS` and surfaced
to callers via :func:`reserved_kind_reason`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ReviewItemKind(StrEnum):
    """Stable identifier for the source of a review item.

    The four members below cover every pending source the project
    currently produces. Two future-only tokens are reserved at the
    parser surface — ``classification`` (blocked on a
    ``ClassificationDecision`` record type) and ``approval-stale``
    (folded into the ``finding`` source once the ``APPROVAL_STALE``
    draft status surfaced as a HIGH-severity finding row).

    Both reserved tokens are recognised by the CLI but currently
    rejected with a ``ReviewKindReservedError`` that names the
    blocking dependency.
    """

    TRANSACTION = "transaction"
    INVOICE = "invoice"
    DIVERGENCE = "divergence"
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
    }
)


def severity_rank(severity: ReviewSeverity) -> int:
    """Return the numeric rank of ``severity`` (CRITICAL=3 .. INFO=0)."""
    return _SEVERITY_RANK[severity]


class ReviewState(StrEnum):
    """Filter state for the review queue CLI.

    ``PENDING`` (default) returns only items that currently want the
    operator's attention. ``ALL`` is reserved for a future "show
    resolved too" mode and is currently identical to ``PENDING``
    because every adapter only emits pending items today.
    """

    PENDING = "pending"
    ALL = "all"


class ReviewFormat(StrEnum):
    """Output format for the review queue CLI."""

    TABLE = "table"
    JSON = "json"


# Reserved-but-unimplemented kind tokens accepted for parsing but
# rejected by the CLI with a descriptive error.
_RESERVED_KINDS: Mapping[str, str] = MappingProxyType(
    {
        "classification": "blocked on ClassificationDecision record",
        "approval-stale": (
            "now surfaced under --kind finding — "
            "drafts with FilingDraftStatus.APPROVAL_STALE emit a HIGH-severity finding row"
        ),
    }
)


def reserved_kind_reason(token: str) -> str | None:
    """Return the blocking reason for a reserved token, or ``None``."""
    return _RESERVED_KINDS.get(token)
