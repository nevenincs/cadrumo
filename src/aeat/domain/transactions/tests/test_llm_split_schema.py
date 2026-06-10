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
from .. import (
    LLMClassifierError,
    LLMSplitChild,
    LLMSplitResponse,
    parse_split_response,
    prompt_spec_with_saturation_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALID_SPLIT_JSON = (
    '{"reason": "two lines on the invoice",'
    ' "children": ['
    '{"proportion": 0.6, "iva_category": "domestic_general_21", "evidence_citation": "line 1"},'
    '{"proportion": 0.4, "iva_category": "domestic_general_21", "evidence_citation": "line 2"}'
    "]}"
)


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


def test_parse_split_extracts_nested_json_amid_prose() -> None:
    noisy = "Here is the split:\n" + _VALID_SPLIT_JSON + "\nHope that helps!"
    response = parse_split_response(noisy, spec=prompt_spec_with_saturation_fields())
    assert len(response.children) == 2
    assert response.children[0].iva_category is IvaCategory.DOMESTIC_GENERAL_21


def test_parse_split_rejects_disallowed_iva_category() -> None:
    # default_prompt_spec has no iva allow-list, so any iva_category is rejected.
    with pytest.raises(LLMClassifierError):
        parse_split_response(_VALID_SPLIT_JSON)


def test_parse_split_no_json_raises() -> None:
    with pytest.raises(LLMClassifierError):
        parse_split_response("no json here", spec=prompt_spec_with_saturation_fields())
