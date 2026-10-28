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

It also owns the one rule for WHO apportions a row once its category is known.
A usage-ratio category (home-office suministros and the dwelling's own costs) is
apportioned by its category rule: the ledger usage-ratio store supplies the
operator's ratio and the registry rule its statutory multiplier, and the
deductibility evaluator applies the product once. A MIXED row's stored
``business_pct`` for such a category is the same number held on the row, so
scaling the row's amounts by it as well would apply the ratio twice
(:func:`row_scaling_proportion`).
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.categories.proportionality import ProportionalityRule
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.irpf_categories import has_activity_irpf_category
from ...domain.transactions.models import Transaction
from .business_proportion import business_proportion

__all__ = [
    "exclusive_business_use",
    "relies_on_activity_marker",
    "renta_expense_business_proportion",
    "row_scaling_proportion",
]

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
            IRPF category establishes full business attribution for a row
            whose classification states none. The Modelo 130 quarterly pago
            fraccionado passes ``True`` (provisional self-assessment); the
            annual Modelo 100 first-slice projection passes ``False``
            (filing-grade, so it requires the business-classification review
            to have resolved the row). A classification that states a
            proportion is never overridden by the marker.

    Returns:
        The proportion of the row attributable to the business, or ``None``
        when the row is not an eligible business expense under the requested
        policy.
    """
    classified = business_proportion(transaction.business_classification, transaction.business_pct)
    if classified is not None:
        # The operator's classification is the specific claim about this row.
        # The marker only stands in for it when the classification gives none,
        # so it cannot lift a MIXED row's share to full attribution.
        return classified
    if accept_activity_marker and has_activity_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
    ):
        return _FULL_BUSINESS_PROPORTION
    return None


def row_scaling_proportion(
    transaction: Transaction,
    proportion: Decimal,
    rule: ProportionalityRule,
) -> Decimal:
    """Return the proportion that scales a row's amounts before its category rule runs.

    ``proportion`` is the eligibility result of :func:`renta_expense_business_proportion`.
    It scales the row's amounts, except for a MIXED row in a usage-ratio category:
    that category rule is the one place the ratio is applied, so the row's amounts
    pass through whole and its stored ``business_pct`` is not multiplied in again.

    Args:
        transaction: The ledger row under consideration.
        proportion: The row's business proportion from the eligibility predicate.
        rule: The proportionality rule of the row's resolved category.

    Returns:
        ``1`` for a MIXED row whose category rule is a usage ratio; otherwise
        ``proportion`` unchanged.
    """
    if transaction.business_classification is BusinessClassification.MIXED and rule.kind.is_usage_ratio:
        return _FULL_BUSINESS_PROPORTION
    return proportion


def exclusive_business_use(transaction: Transaction) -> bool:
    """Return whether an eligible row states that its element serves only the activity.

    The row's classification is the operator's statement of use. A MIXED row
    states shared use with private needs; a BUSINESS row, or a row the
    actividad marker admits without a split, states use for the activity alone.
    A category whose rule requires exclusive use (a vehicle, a mobile line)
    reads this, because an indivisible element admits no partial affectation
    (RIRPF art. 22.3).

    Args:
        transaction: A row that already passed
            :func:`renta_expense_business_proportion`.

    Returns:
        ``False`` for a MIXED row; ``True`` otherwise.
    """
    return transaction.business_classification is not BusinessClassification.MIXED
