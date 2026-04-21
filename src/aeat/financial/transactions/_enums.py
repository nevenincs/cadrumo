"""Closed enumerations for transaction records."""

from __future__ import annotations

from enum import StrEnum


class TransactionDirection(StrEnum):
    """Supported transaction directions."""

    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"


class BusinessClassification(StrEnum):
    """Supported business-classification states.

    `BUSINESS` / `PERSONAL` / `MIXED` are the three *classified* outcomes.
    `NOT_YET_PROCESSED`, `PROCESSED_UNCLASSIFIED`, `SKIPPED_BY_RULE`, and
    `FAILED_VALIDATION` each capture a distinct pipeline state so Kent can
    answer "did the pipeline look at this, and what did it decide?" without
    the ambiguity of the legacy `UNCLASSIFIED` value (see issue #237 and
    .vault/adr/2026-04-18-unclassified-state-adr.md).
    """

    BUSINESS = "BUSINESS"
    PERSONAL = "PERSONAL"
    MIXED = "MIXED"
    NOT_YET_PROCESSED = "NOT_YET_PROCESSED"
    PROCESSED_UNCLASSIFIED = "PROCESSED_UNCLASSIFIED"
    SKIPPED_BY_RULE = "SKIPPED_BY_RULE"
    FAILED_VALIDATION = "FAILED_VALIDATION"


CLASSIFIED_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
    }
)


def is_classified(state: BusinessClassification) -> bool:
    """Return ``True`` when the pipeline has produced a classified outcome."""
    return state in CLASSIFIED_STATES


LEGACY_UNCLASSIFIED_ALIAS: str = "UNCLASSIFIED"
"""String value emitted by catalogues prior to #237. Aliases to ``NOT_YET_PROCESSED`` on load."""
