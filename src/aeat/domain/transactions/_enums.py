"""Closed enumerations for the transaction catalogue.

Defines the closed discriminators on
:class:`aeat.domain.transactions.Transaction` and related history records.
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


class TransactionLifecycleState(StrEnum):
    """Supported lifecycle states for one ledger transaction row.

    Attributes:
        ACTIVE: The row participates in every default list, every tax
            aggregation, and every readiness check. The only state in
            which `update_manual_transaction` accepts a mutation.
        ARCHIVED: Operator chose to remove the row from default
            attention without deleting it. Reversible.
        STASHED: Operator parked the row pending classification or
            review. Reversible.
        SPLIT: The row is the parent of an N-way split; its amount
            has been redistributed into ``N`` child rows that now
            carry the active balance. The parent is preserved for
            audit lineage. A SPLIT row is invisible to default lists,
            tax aggregations, and readiness checks; only the
            ``merge_transactions`` action can transition a SPLIT
            parent back to ARCHIVED (never to ACTIVE).
    """

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    STASHED = "STASHED"
    SPLIT = "SPLIT"


class SplitRole(StrEnum):
    """Role of a transaction within a split-lineage relationship.

    Attributes:
        PARENT: The original row whose amount was redistributed.
            Carries the canonical ``split_group_id`` and the full
            tuple of child ids in ``sibling_transaction_ids``.
        CHILD: One of the N derived rows produced by a split. Sums of
            every CHILD amount under one ``split_group_id`` equal the
            PARENT amount exactly. Carries the parent id plus every
            other child id in ``sibling_transaction_ids``.
        MERGED: A new row produced by re-merging a complete cohort
            of CHILD rows. The PARENT transitions to ARCHIVED; the
            CHILD rows transition to ARCHIVED; the MERGED row carries
            a fresh content-addressed id and the merged-cohort ids
            in ``sibling_transaction_ids``.
    """

    PARENT = "PARENT"
    CHILD = "CHILD"
    MERGED = "MERGED"


CLASSIFIED_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
    },
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
