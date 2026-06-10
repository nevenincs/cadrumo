"""Schema tests for the evidence-driven N-way split proposal.

The model proposes proportions (fractions), category, and iva_category per child;
it never carries a euro amount or a regulated tax number. The application derives
amounts from the parent gross and the tax substrate from the registry.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...iva import IvaCategory
from .. import LLMSplitChild, LLMSplitResponse

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _child(proportion: str) -> LLMSplitChild:
    return LLMSplitChild(proportion=Decimal(proportion), iva_category=IvaCategory.DOMESTIC_GENERAL_21)


def test_valid_two_way_split_builds() -> None:
    response = LLMSplitResponse(
        children=(_child("0.6"), _child("0.4")),
        reason="invoice has a business line and a personal line",
    )
    assert len(response.children) == 2
    assert sum(c.proportion for c in response.children) == Decimal("1.0")


def test_split_requires_at_least_two_children() -> None:
    with pytest.raises(ValidationError):
        LLMSplitResponse(children=(_child("1.0"),), reason="single child")


def test_proportions_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        LLMSplitResponse(children=(_child("0.6"), _child("0.6")), reason="oversum")


def test_child_proportion_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        LLMSplitChild(proportion=Decimal("0"))
    with pytest.raises(ValidationError):
        LLMSplitChild(proportion=Decimal("1.5"))


@pytest.mark.parametrize("numeric_field", ["amount", "iva_amount", "taxable_base", "iva_rate"])
def test_split_child_structurally_refuses_numeric_fields(numeric_field: str) -> None:
    with pytest.raises(ValidationError):
        LLMSplitChild.model_validate({"proportion": "0.5", numeric_field: "100.00"})
