"""Generic predicate adapter for registry-projected IVA classification rows.

Concrete invoice predicates and the ordered classification catalogue live in
the versioned registry. This module only provides the callable shape used by a
consumer that has projected one of those declarations into Python mechanics.
"""

from __future__ import annotations

from collections.abc import Callable

from .classification import IvaInvoiceClassificationCriteria

IvaClassificationPredicate = Callable[[IvaInvoiceClassificationCriteria], bool]


def evaluate_classification_predicate(
    predicate: IvaClassificationPredicate,
    criteria: IvaInvoiceClassificationCriteria,
) -> bool:
    """Evaluate one caller-supplied predicate against typed criteria."""
    return bool(predicate(criteria))


__all__ = ["IvaClassificationPredicate", "evaluate_classification_predicate"]
