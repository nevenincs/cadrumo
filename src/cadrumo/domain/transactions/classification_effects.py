"""What a row's classification and direction decide about its other facts.

These are the answers every write path, correlation and frontend asks of the
same relationship: which values a classification write drops, and which rows
read a spending category.
"""

from __future__ import annotations

from typing import Final, Literal

from .enums import (
    BUSINESS_BEARING_STATES,
    CHANGEABLE_LIFECYCLE_STATES,
    TRANSFER_ALLOWED_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
    takes_business_share,
)

LifecycleAction = Literal["archive", "stash", "restore", "exclude"]
"""A change of a row's lifecycle a person can ask for."""

SHARE_DEPENDENT_FIELDS: Final[frozenset[str]] = frozenset({"business_pct", "usage_ratio_id"})
"""What only a share-bearing classification keeps."""

BUSINESS_DEPENDENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "category_id",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "recargo_amount",
        "irpf_category",
        "m210_income_classification",
        "prorrata_reference",
    }
)
"""What only a business-bearing classification keeps."""


def fields_cleared_by_classification(classification: BusinessClassification) -> frozenset[str]:
    """Return the values a write of ``classification`` drops from the row.

    A classification that bears no share drops the share and its usage ratio;
    one with no business component also drops the business figures.
    """
    cleared = frozenset[str]()
    if not takes_business_share(classification):
        cleared |= SHARE_DEPENDENT_FIELDS
    if classification not in BUSINESS_BEARING_STATES:
        cleared |= BUSINESS_DEPENDENT_FIELDS
    return cleared


def takes_expense_category(direction: TransactionDirection, *, has_purchase_evidence: bool) -> bool:
    """Return whether a row feeds the deductible-expense pipeline and so reads a spending category.

    ``category_id`` is a deductible-expense taxonomy. The Renta expense
    aggregation that consumes it admits only OUTGOING rows (expenses) and
    INCOMING rows carrying purchase-invoice evidence (expense refunds). Pure
    income is classified by its direction alone.
    """
    if direction is TransactionDirection.OUTGOING:
        return True
    return direction is TransactionDirection.INCOMING and has_purchase_evidence


def takes_changes(lifecycle: TransactionLifecycleState) -> bool:
    """Return whether a row in ``lifecycle`` takes a change to its facts."""
    return lifecycle in CHANGEABLE_LIFECYCLE_STATES


def takes_classification(direction: TransactionDirection, classification: BusinessClassification) -> bool:
    """Return whether a row going ``direction`` may be classified as ``classification``."""
    return direction is not TransactionDirection.INTERNAL_TRANSFER or classification in TRANSFER_ALLOWED_STATES


def takes_invoice(direction: TransactionDirection) -> bool:
    """Return whether a row going ``direction`` is offered an invoice to settle.

    Narrower than the link writer, which does not look at direction.
    """
    return direction is not TransactionDirection.INTERNAL_TRANSFER


def takes_m210_income(direction: TransactionDirection) -> bool:
    """Return whether a row going ``direction`` can carry Modelo 210 income."""
    return direction is TransactionDirection.INCOMING


def awaits_invoice(
    lifecycle: TransactionLifecycleState,
    direction: TransactionDirection,
    classification: BusinessClassification,
    *,
    linked: bool,
) -> bool:
    """Return whether a row still waits for its invoice: an active business row, no transfer, with none linked."""
    return (
        not linked
        and takes_changes(lifecycle)
        and takes_invoice(direction)
        and classification in BUSINESS_BEARING_STATES
    )


def advises_purchase_evidence(
    lifecycle: TransactionLifecycleState,
    direction: TransactionDirection,
    classification: BusinessClassification,
    *,
    has_evidence: bool,
) -> bool:
    """Return whether a row should be told it has no purchase document; advice, never a block."""
    return (
        not has_evidence
        and takes_changes(lifecycle)
        and direction is TransactionDirection.OUTGOING
        and classification in BUSINESS_BEARING_STATES
    )


def lifecycle_actions_taken(
    lifecycle: TransactionLifecycleState, classification: BusinessClassification
) -> tuple[LifecycleAction, ...]:
    """Return the lifecycle actions a person is offered on a row in this state.

    Narrower than the lifecycle writer, which also takes a stashed row to archived.
    Whether a finalized declaration seals the row is a separate fact.
    """
    if lifecycle in {TransactionLifecycleState.ARCHIVED, TransactionLifecycleState.STASHED}:
        return ("restore",)
    if not takes_changes(lifecycle):
        return ()
    if classification is BusinessClassification.REVIEWED_EXCLUDED:
        return ("archive", "stash")
    return ("archive", "stash", "exclude")


__all__ = [
    "BUSINESS_DEPENDENT_FIELDS",
    "SHARE_DEPENDENT_FIELDS",
    "LifecycleAction",
    "advises_purchase_evidence",
    "awaits_invoice",
    "fields_cleared_by_classification",
    "lifecycle_actions_taken",
    "takes_changes",
    "takes_classification",
    "takes_expense_category",
    "takes_invoice",
    "takes_m210_income",
]
