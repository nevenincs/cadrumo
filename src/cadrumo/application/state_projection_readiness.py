"""Classify the operator input channel of a binding missing from a readiness projection."""

from __future__ import annotations


def readiness_binding_input_channel(
    binding_id: str,
    *,
    enum_consumed: set[str],
    date_consumed: set[str],
) -> str:
    """Return the operator input channel declared for one missing binding."""
    if binding_id in date_consumed:
        return "date"
    if binding_id in enum_consumed:
        return "enum"
    return "decimal"
