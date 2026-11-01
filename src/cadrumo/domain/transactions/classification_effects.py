"""What a row's classification and direction decide about its other facts.

These are the answers every write path, correlation and frontend asks of the
same relationship: which values a classification write drops, and which rows
read a spending category.
"""

from __future__ import annotations

from typing import Final

from .enums import BUSINESS_BEARING_STATES, BusinessClassification, TransactionDirection, takes_business_share

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
    cleared: frozenset[str] = frozenset()
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


__all__ = [
    "BUSINESS_DEPENDENT_FIELDS",
    "SHARE_DEPENDENT_FIELDS",
    "fields_cleared_by_classification",
    "takes_expense_category",
]
