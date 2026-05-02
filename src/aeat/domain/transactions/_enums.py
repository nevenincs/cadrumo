"""Closed enumerations for the transaction catalogue.

Defines :class:`TransactionDirection` and :class:`BusinessClassification`,
the only sanctioned discriminators on
:class:`aeat.domain.transactions.Transaction` and
:class:`aeat.domain.transactions.ClassificationHistoryEntry`.
"""

from __future__ import annotations

from enum import StrEnum


class TransactionDirection(StrEnum):
    """Supported transaction directions.

    Attributes:
        INCOMING: Money credited to the autónomo's account.
        OUTGOING: Money debited from the autónomo's account.
        INTERNAL_TRANSFER: Movement between two of the autónomo's own
            accounts; never tax-relevant on its own.
    """

    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"


class BusinessClassification(StrEnum):
    """Supported business-classification states.

    The three *classified* outcomes are :attr:`BUSINESS`,
    :attr:`PERSONAL`, and :attr:`MIXED`. The remaining four members
    each capture a distinct pipeline state so a downstream consumer
    can answer "did the pipeline look at this, and what did it
    decide?" without ambiguous catch-all values.

    Attributes:
        BUSINESS: Certain business expense or income.
        PERSONAL: Certain personal expense or income.
        MIXED: Partially business, partially personal; requires a
            ``business_pct`` companion in ``[0, 1]``.
        NOT_YET_PROCESSED: Pipeline has not yet evaluated this
            transaction; the default state on import.
        PROCESSED_UNCLASSIFIED: Classifier ran but could not decide.
        SKIPPED_BY_RULE: A rule explicitly skipped this transaction.
        FAILED_VALIDATION: Classifier output failed validation; the
            pipeline preserves the prior decision.
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
"""Frozen set of :class:`BusinessClassification` values that count as
classified outcomes for downstream rollups."""


def is_classified(state: BusinessClassification) -> bool:
    """Return ``True`` when the pipeline has produced a classified outcome.

    Args:
        state: A :class:`BusinessClassification` value.

    Returns:
        ``True`` iff ``state`` is one of :attr:`BusinessClassification.BUSINESS`,
        :attr:`BusinessClassification.PERSONAL`, or
        :attr:`BusinessClassification.MIXED`.
    """
    return state in CLASSIFIED_STATES


"""String value emitted by older catalogues. Aliases to
:attr:`BusinessClassification.NOT_YET_PROCESSED` on load."""
