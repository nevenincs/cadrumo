"""A fault says where, what kind and what the validator said, and never attaches the refused input."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ..errors.error_codes import build_error_envelope
from ..models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..period import Period, PeriodError
from ..request_faults import MAX_REQUEST_FAULTS, RequestFault, registered_error_fault, request_faults

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
            raise ValueError(f"holder {value} is not registered; registered holders: somebody, anybody")
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


def _refused(document: object) -> ValidationError:
    with pytest.raises(ValidationError) as refused:
        _Request.model_validate_json(json.dumps(document))
    return refused.value


def _faults(document: object) -> tuple[RequestFault, ...]:
    return request_faults(_refused(document))


def _by_location(faults: tuple[RequestFault, ...]) -> dict[tuple[str | int, ...], RequestFault]:
    return {fault.location: fault for fault in faults}


def test_a_missing_an_unknown_and_a_mistyped_member_are_each_located_and_named() -> None:
    faults = _by_location(_faults({"lines": [{"amount": 5, "holder": "somebody"}], "extra": _PRIVATE}))

    assert faults[("action",)].type == "missing"
    assert faults[("extra",)].type == "extra_forbidden"
    assert faults[("lines", 0, "amount")].type == "string_type"
    assert all(fault.message for fault in faults.values())


def test_a_fault_gives_the_validators_own_message() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": "nobody"}]})

    assert fault.location == ("lines", 0, "holder")
    assert (fault.type, fault.message) == ("value_error", "Value error, a line names the person who holds it")


def test_a_message_that_quotes_the_refused_value_and_gives_guidance_is_carried_as_the_validator_wrote_it() -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": _PRIVATE}]})

    assert fault.location == ("lines", 0, "holder")
    assert (fault.type, fault.message) == (
        "value_error",
        f"Value error, holder {_PRIVATE} is not registered; registered holders: somebody, anybody",
    )


def test_a_message_about_the_whole_request_is_carried_as_the_validator_wrote_it() -> None:
    (fault,) = _faults({"action": "list", "reference": _PRIVATE})

    assert fault.location == ()
    assert (fault.type, fault.message) == ("value_error", "Value error, action 'list' takes no reference")


def test_every_fault_is_the_location_kind_and_message_the_model_reported() -> None:
    documents: tuple[object, ...] = (
        {"lines": [{"amount": 5, "holder": _PRIVATE}], "extra": 1},
        {"action": "list", "reference": "r"},
        {"action": "add", "lines": [{"amount": "123456789012", "holder": "nobody"}]},
        [_PRIVATE],
    )

    for document in documents:
        refused = _refused(document)
        reported = [(detail["loc"], detail["type"], detail["msg"]) for detail in refused.errors()]

        assert [(fault.location, fault.type, fault.message) for fault in request_faults(refused)] == reported


def test_no_fault_attaches_the_refused_input_the_error_context_or_the_documentation_link() -> None:
    # No validator of the model words these refusals, so the private text is in the model's report as input alone.
    documents: tuple[object, ...] = (
        {"action": _PRIVATE},
        {"action": "add", "lines": [{"amount": _PRIVATE, "holder": "somebody"}]},
        {"action": "add", "lines": _PRIVATE},
        {"action": "add", "reference": [_PRIVATE]},
        [_PRIVATE],
        _PRIVATE,
    )

    for document in documents:
        refused = _refused(document)
        assert _PRIVATE in json.dumps(refused.errors(include_url=False, include_context=False), default=str), document
        faults = request_faults(refused)
        assert faults, document
        for fault in faults:
            assert set(fault.model_dump(mode="json")) == {"location", "type", "message"}
        assert _PRIVATE not in json.dumps([fault.model_dump(mode="json") for fault in faults]), document


def test_a_request_with_many_faults_is_told_a_bounded_number_of_them() -> None:
    lines = [{"amount": "1", "holder": "nobody"} for _ in range(MAX_REQUEST_FAULTS + 9)]

    faults = _faults({"action": "add", "lines": lines})

    assert len(faults) == MAX_REQUEST_FAULTS
    assert [fault.location for fault in faults] == [("lines", index, "holder") for index in range(MAX_REQUEST_FAULTS)]


@pytest.mark.parametrize("member", ["input", "ctx", "url"])
def test_a_fault_is_a_closed_record_of_three_members(member: str) -> None:
    (fault,) = _faults({"action": "add", "lines": [{"amount": "1", "holder": "nobody"}]})
    document = fault.model_dump(mode="json")

    assert set(document) == {"location", "type", "message"}
    assert RequestFault.model_validate_json(fault.model_dump_json()) == fault
    with pytest.raises(ValidationError, match="extra_forbidden"):
        RequestFault.model_validate_json(json.dumps(document | {member: "anything"}))


def test_a_registered_error_is_one_fault_for_the_whole_request_with_the_code_and_message_the_command_line_prints() -> (
    None
):
    with pytest.raises(PeriodError) as raised:
        Period.from_year_and_code(2025, "evento")
    printed = build_error_envelope(raised.value)

    fault = registered_error_fault(raised.value)

    assert "EVENT-N" in printed.message
    assert (fault.location, fault.type, fault.message) == ((), "INTEGRITY_PERIOD", printed.message)
