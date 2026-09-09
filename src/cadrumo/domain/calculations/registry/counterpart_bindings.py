"""Validation for reserved counterpart-source registry bindings."""

from __future__ import annotations

from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .invoice_bindings import (
    InvoiceSelector,
    invoice_selector,
    validate_invoice_family_fact_and_aggregation,
)
from .schema import DataBindingDefinition


def _validated_counterpart_selector(binding: DataBindingDefinition) -> InvoiceSelector:
    selector = invoice_selector(binding)
    validate_invoice_family_fact_and_aggregation(
        binding,
        selector,
        family_label="counterpart aggregation",
        strict_scalar_shape=False,
    )
    return selector


def validate_counterpart_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a reserved counterpart-source declaration at registry build time."""
    failures = selector_against_model(binding, InvoiceSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "counterpart", _validated_counterpart_selector)


__all__ = ["validate_counterpart_binding"]
