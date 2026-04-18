"""Closed enumerations for the unified review queue.

See [[2026-04-18-unified-review-queue-adr]] decision D5 for the
kind, severity, and state taxonomy.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ReviewItemKind(StrEnum):
    """Stable identifier for the source of a review item.

    The five members below cover every pending source the project
    currently produces. Two future-only members are reserved by the
    ADR (see [[2026-04-18-unified-review-queue-adr#kind-namespace-reservations]]):

    - ``classification`` — blocked on the ``ClassificationDecision``
      record type (umbrella #202 child C4h).
    - ``approval-stale`` — blocked on ``FilingDraftStatus.APPROVED``
      (#230) and the staleness detector (C4f).

    Both reserved tokens are recognised by the CLI but currently
    rejected with a ``ReviewKindReservedError`` that names the
    blocking issue.
    """

    TRANSACTION = "transaction"
    INVOICE = "invoice"
    DIVERGENCE = "divergence"
    FINDING = "finding"
    INBOX = "inbox"


class ReviewSeverity(StrEnum):
    """Editorial severity of a review item.

    Severity is derived per-source by the adapter (see ADR D5),
    not stored on the underlying record. The ranking is fixed:
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

    ``PENDING`` (default) returns only items that currently want
    Kent's attention. ``ALL`` is reserved for a future "show
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
        "classification": "blocked on ClassificationDecision record (umbrella #202 child C4h)",
        "approval-stale": (
            "now surfaced under --kind finding since #230 shipped — "
            "drafts with FilingDraftStatus.APPROVAL_STALE emit a HIGH-severity finding row"
        ),
    }
)


def reserved_kind_reason(token: str) -> str | None:
    """Return the blocking reason for a reserved token, or ``None``."""
    return _RESERVED_KINDS.get(token)
