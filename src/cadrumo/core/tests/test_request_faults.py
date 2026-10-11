"""A request model's faults say where, what kind and why, and never the value that was refused."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ..models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..request_faults import MAX_REQUEST_FAULTS, VALUE_FREE_FAULT_MESSAGE, RequestFault, request_faults

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRIVATE = "synthetic-private-holder-5c1e"


class _Line(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    amount: Annotated[str, Field(max_length=8)]
    holder: str

    @field_validator("holder")
    @classmethod
    def _holder_is_known(cls, value: str) -> str:
        if value.startswith("synthetic-private"):
            raise ValueError(f"holder {value} is not registered")
        if value == "nobody":
            raise ValueError("a line names the person who holds it")
        return value


class _Request(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["add", "list"]
    lines: tuple[_Line, ...] = ()
    reference: str | None = None

    @model_validator(mode="after")
    def _a_listing_takes_no_reference(self) -> _Request:
        if self.action == "list" and self.reference is not None:
            raise ValueError(f"action {self.action!r} takes no reference")
        return self


def _faults(document: object) -> tuple[RequestFault, ...]:
    with pytest.raises(ValidationError) as refused:
        _Request.model_validate_json(json.dumps(document))
    return request_faults(refused.value)


def _by_location(faults: tuple[RequestFault, ...]) -> dict[tuple[str | int, ...], RequestFault]:
    return {fault.location: fault for fault in faults}


def test_a_missing_an_unknown_and_a_mistyped_member_are_each_located_and_named() -> None:
    faults = _by_location(_faults({"lines": [{"amount": 5, "holder": "somebody"}], "extra": _PRIVATE}))

    assert faults[("action",)].type == "missing"
    assert faults[("extra",)].type == "extra_forbidden"
    assert faults[("lines", 0, "amount")].type == "string_type"
    assert all(fault.message for fault in faults.values())
    assert _PRIVATE not in json.dumps([fault.model_dump(mode="json") for fault in faults.values()])


def test_the_models_own_wording_is_kept_when_it_says_nothing_of_the_value() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": "nobody"}]})

    assert fault.location == ("lines", 0, "holder")
    assert (fault.type, fault.message) == ("value_error", "Value error, a line names the person who holds it")


def test_wording_that_repeats_the_refused_value_is_replaced_and_the_location_and_kind_stay() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": _PRIVATE}]})

    assert fault.location == ("lines", 0, "holder")
    assert (fault.type, fault.message) == ("value_error", VALUE_FREE_FAULT_MESSAGE)


def test_wording_that_repeats_a_member_of_a_refused_request_is_replaced() -> None:
    (fault,) = _faults({"action": "list", "reference": _PRIVATE})

    assert fault.location == ()
    assert (fault.type, fault.message) == ("value_error", VALUE_FREE_FAULT_MESSAGE)


def test_a_rule_about_length_names_the_bound_and_not_the_text_that_broke_it() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "123456789012", "holder": "somebody"}]})

    assert fault.type == "string_too_long"
    assert "8" in fault.message and "123456789012" not in fault.message


def test_no_fault_of_any_kind_repeats_a_private_value() -> None:
    documents: tuple[object, ...] = (
        {"action": _PRIVATE},
        {"action": "add", "lines": [{"amount": _PRIVATE, "holder": _PRIVATE}]},
        {"action": "add", "lines": _PRIVATE},
        {"action": "list", "reference": _PRIVATE, _PRIVATE: 1},
        [_PRIVATE],
        _PRIVATE,
    )

    for document in documents:
        faults = _faults(document)
        assert faults, document
        # A member name that is not the model's is the caller's own spelling and locates the fault.
        messages = json.dumps([[fault.type, fault.message] for fault in faults])
        assert _PRIVATE not in messages, document


def test_a_refused_input_too_large_to_read_through_is_answered_without_the_models_wording() -> None:
    many = [{"amount": "1", "holder": f"holder-{index}"} for index in range(3000)]

    (fault,) = _faults({"action": "list", "reference": "r", "lines": many})

    assert (fault.location, fault.message) == ((), VALUE_FREE_FAULT_MESSAGE)


def test_a_request_with_many_faults_is_told_a_bounded_number_of_them() -> None:
    lines = [{"amount": "1", "holder": "nobody"} for _ in range(MAX_REQUEST_FAULTS + 9)]

    faults = _faults({"action": "add", "lines": lines})

    assert len(faults) == MAX_REQUEST_FAULTS
    assert [fault.location for fault in faults] == [("lines", index, "holder") for index in range(MAX_REQUEST_FAULTS)]


def test_a_fault_is_a_closed_record_of_three_members() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": "nobody"}]})

    assert set(fault.model_dump(mode="json")) == {"location", "type", "message"}
    assert RequestFault.model_validate_json(fault.model_dump_json()) == fault
