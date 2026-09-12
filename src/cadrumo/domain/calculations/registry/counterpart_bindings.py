"""Validation for reserved counterpart-source registry bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .invoice_bindings import (
    InvoiceProviderBase,
    invoice_selector,
    validate_invoice_family_fact_and_aggregation,
)

if TYPE_CHECKING:
    from .schema import BindingDefinition


def _validated_counterpart_selector(binding: BindingDefinition) -> InvoiceProviderBase:
    selector = invoice_selector(binding)
    validate_invoice_family_fact_and_aggregation(
        binding,
        selector,
        family_label="counterpart aggregation",
        strict_scalar_shape=False,
    )
    return selector


def validate_counterpart_binding(binding: BindingDefinition) -> list[str]:
    """Validate a reserved counterpart-source declaration at registry build time."""
    failures = selector_against_model(binding, InvoiceProviderBase)
    if failures:
        return failures
    return invariant_diagnostics(binding, "counterpart", _validated_counterpart_selector)


__all__ = ["validate_counterpart_binding"]
