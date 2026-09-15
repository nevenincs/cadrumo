"""Registry-projected entry point for IVA classification tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..classification import classify_iva, resolve_iva_classification_inputs

if TYPE_CHECKING:
    from ...calculations.registry.authority import PinnedAuthorityOperation
    from ..classification import IvaClassificationResult, IvaInvoiceClassificationCriteria


def classify_with_registry_rules(
    criteria: IvaInvoiceClassificationCriteria,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationResult:
    """Classify through the rules, rate mapping and territories the pinned registry projects."""
    inputs = resolve_iva_classification_inputs(effective_date=criteria.transaction_date, operation=operation)
    return classify_iva(
        criteria,
        rules=inputs.rules,
        rate_categories=inputs.rate_categories,
        rate_territories=inputs.rate_territories,
        operation=operation,
    )
