"""Tests for shared binding selector projection helpers."""

from __future__ import annotations

from typing import Any

import pytest

from .....core import BindingSourceKind
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from ..binding_selector_utils import BindingRowSetSelector, binding_row_set_selector
from ..errors import RegistryValidationError
from ..schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _binding(
    selector: dict[str, Any],
    *,
    source: BindingSourceKind = BindingSourceKind.WITHHOLDING,
    aggregation: BindingAggregation | None = None,
) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "binding-under-test",
            "source": source,
            "selector": selector,
            "aggregation": aggregation,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-190",),
        },
    )


def test_binding_row_set_selector_returns_none_for_an_eligible_binding_with_no_claim() -> None:
    """A row-set-eligible binding that declares none of the row-set keys is ``None``, not refused."""
    binding = _binding(
        {"fact": "perceptor_count"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    assert binding_row_set_selector(binding) is None


def test_binding_row_set_selector_accepts_row_field_projection() -> None:
    binding = _binding(
        {
            "fact": "row_field",
            "row_field": "perceptor_tax_id",
            "grouping": "per_perceptor",
            "record": "perceptor",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    selector = binding_row_set_selector(binding)

    assert isinstance(selector, BindingRowSetSelector)
    assert selector.fact == "row_field"
    assert selector.row_field == "perceptor_tax_id"
    assert selector.grouping == "per_perceptor"
    assert selector.record == "perceptor"


def test_binding_row_set_selector_rejects_a_non_row_set_eligible_binding() -> None:
    """A binding whose aggregation op is not ``rows`` is refused by name.

    This binding declares export-shaped keys (``field``/``offset``/``length``/
    ``data_type``), not a row-set claim -- exactly the shape that used to be
    silently accepted as "no row-set projection" before the precondition moved
    into the callee. It is now refused for the real reason (not row-set
    eligible) rather than answering a question it was never asked.
    """
    binding = _binding(
        {
            "record": "operador",
            "field": "base_imponible",
            "offset": 42,
            "length": 12,
            "data_type": "money",
        },
        source=BindingSourceKind.MANUAL_INPUT,
    )

    with pytest.raises(RegistryValidationError, match="is not row-set-eligible"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_row_fact_without_grouping() -> None:
    binding = _binding(
        {"fact": "row_field", "row_field": "perceptor_tax_id"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="missing grouping"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_grouping_with_non_row_fact() -> None:
    binding = _binding(
        {"fact": "perceptor_count", "grouping": "per_perceptor", "row_field": "perceptor_tax_id"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="non-row fact"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_non_row_fact_with_row_keys() -> None:
    binding = _binding(
        {"fact": "perceptor_count", "grouping": "per_perceptor"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="non-row fact"):
        binding_row_set_selector(binding)
