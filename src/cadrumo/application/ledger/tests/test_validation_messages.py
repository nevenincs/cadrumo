"""Bounded, field-located refusal messages shared by ledger operations."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..validation_messages import bounded_validation_messages

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Line(BaseModel):
    amount: int = Field(ge=0)


class _Patch(BaseModel):
    description: str
    lines: list[_Line]

    @field_validator("description")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be blank")
        return value


def _validation_error(payload: object) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        _Patch.model_validate(payload)
    return caught.value


def test_pydantic_refusals_keep_dotted_locations_and_strip_the_value_error_prefix() -> None:
    error = _validation_error({"description": " ", "lines": [{"amount": 1}, {"amount": -2}]})

    messages = bounded_validation_messages(error, limit=8, fallback="unused")

    assert messages == (
        "description: description must not be blank",
        "lines.1.amount: Input should be greater than or equal to 0",
    )


def test_pydantic_refusals_never_echo_the_rejected_input() -> None:
    rejected = "ES9121000418450200051332"
    error = _validation_error({"description": " ", "lines": [{"amount": rejected}]})

    messages = bounded_validation_messages(error, limit=8, fallback="unused")

    assert messages
    assert all(rejected not in message for message in messages)


def test_the_limit_bounds_how_many_entries_are_kept() -> None:
    error = _validation_error({"description": " ", "lines": [{"amount": -1}, {"amount": -2}, {"amount": -3}]})

    assert len(bounded_validation_messages(error, limit=2, fallback="unused")) == 2


def test_other_errors_keep_their_own_sentence_truncated_to_a_fixed_length() -> None:
    long_sentence = "x" * 3000

    assert bounded_validation_messages(ValueError("  prefix not found  "), limit=4, fallback="unused") == (
        "prefix not found",
    )
    assert bounded_validation_messages(ValueError(long_sentence), limit=4, fallback="unused") == ("x" * 2048,)


def test_an_error_with_no_usable_detail_reports_the_fallback() -> None:
    assert bounded_validation_messages(ValueError("   "), limit=4, fallback="values were invalid") == (
        "values were invalid",
    )
