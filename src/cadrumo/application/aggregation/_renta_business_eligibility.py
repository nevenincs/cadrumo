"""One business-eligibility predicate for both Renta expense projections.

The Modelo 130 gasto pipeline and the annual Modelo 100 first-slice expense
pipeline both decide whether a ledger row is a business expense and, if so, at
what proportion. They decided it with two separate implementations that
disagreed: M130 honoured an explicit ``actividad_economica`` IRPF category as
full business attribution, while M100 consulted the business classification
alone. A row carrying the activity marker but not yet swept by the
business-classification review was therefore accepted by the quarterly pago
fraccionado and rejected by the annual declaration built from the same ledger.

The divergence itself is legitimate: the quarterly pago fraccionado is a
provisional self-assessment, while the annual declaration is the filing-grade
one and may reasonably demand the review. What was wrong is that the
difference lived in two predicates that could drift independently, and that
the annual refusal was reported as a generic "unclassified" state -- the same
reason a row with no classification signal at all produces -- so the operator
could not tell that the row WAS activity-marked and needed only review.

This module is the one predicate. The annual gate is now a declared argument
of it, and :func:`relies_on_activity_marker` names the state the annual
pipeline reports specifically.
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.irpf_categories import has_activity_irpf_category
from ...domain.transactions.models import Transaction
from ._business_proportion import business_proportion

__all__ = ["relies_on_activity_marker", "renta_expense_business_proportion"]

_FULL_BUSINESS_PROPORTION = Decimal("1")


def relies_on_activity_marker(transaction: Transaction) -> bool:
    """Return whether eligibility rests only on the explicit actividad marker.

    True when the row carries the ``actividad_economica`` IRPF category but its
    business classification alone would not make it a business expense. This is
    exactly the state the two pipelines answer differently, so it is named once
    here rather than re-derived at each caller.

    A reviewed exclusion is never in this state: the operator's final
    disposition outranks the category tag, and callers short-circuit it before
    reaching this module.
    """
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return False
    if not has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return False
    return business_proportion(transaction.business_classification, transaction.business_pct) is None


def renta_expense_business_proportion(
    transaction: Transaction,
    *,
    accept_activity_marker: bool,
) -> Decimal | None:
    """Return the business-attributed proportion of ``transaction``, or ``None``.

    Args:
        transaction: The ledger row under consideration.
        accept_activity_marker: Whether an explicit ``actividad_economica``
            IRPF category alone establishes full business attribution. The
            Modelo 130 quarterly pago fraccionado passes ``True`` (provisional
            self-assessment); the annual Modelo 100 first-slice projection
            passes ``False`` (filing-grade, so it requires the
            business-classification review to have resolved the row).

    Returns:
        The proportion of the row attributable to the business, or ``None``
        when the row is not an eligible business expense under the requested
        policy.
    """
    if accept_activity_marker and has_activity_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
    ):
        return _FULL_BUSINESS_PROPORTION
    return business_proportion(transaction.business_classification, transaction.business_pct)
