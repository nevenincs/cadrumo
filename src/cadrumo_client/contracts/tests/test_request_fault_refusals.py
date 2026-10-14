"""Only a refusal of an invalid request carries faults, and a fault on the wire is its three members alone."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.request_faults import RequestFault

from ..contracts import RefusalCode
from ..profile_access import AccessRefusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MESSAGE = "Value error, own account action 'list' takes no account id"
"""A validator's message as written, quoting what it refused."""

_FAULT = RequestFault(location=("patch", "taxable_base"), type="value_error", message=_MESSAGE)


def _refusal(code: AccessDenialCode | AutomationCustodyCode | RefusalCode, *faults: RequestFault) -> AccessRefusal:
    return AccessRefusal(
        request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), code=code, request_faults=faults
    )


def test_an_invalid_refusal_carries_its_faults_through_the_wire_document() -> None:
    refusal = _refusal(AutomationCustodyCode.INVALID, _FAULT)

    read_back = AccessRefusal.model_validate_json(refusal.model_dump_json())

    assert read_back.request_faults == (_FAULT,)
    assert read_back.request_faults[0].model_dump(mode="json") == {
        "location": ["patch", "taxable_base"],
        "type": "value_error",
        "message": _MESSAGE,
    }


@pytest.mark.parametrize("member", ["input", "ctx", "url"])
def test_a_wire_document_whose_fault_attaches_the_refused_input_its_context_or_its_link_is_refused(member: str) -> None:
    document = json.loads(_refusal(AutomationCustodyCode.INVALID, _FAULT).model_dump_json())
    document["request_faults"][0][member] = {"refused": "payload"}

    with pytest.raises(ValidationError, match="extra_forbidden"):
        AccessRefusal.model_validate_json(json.dumps(document))


def test_a_refusal_with_no_faults_says_so() -> None:
    assert _refusal(AutomationCustodyCode.INVALID).request_faults == ()
    assert _refusal(AccessDenialCode.PROFILE_MISMATCH).request_faults == ()


@pytest.mark.parametrize(
    "code", [AccessDenialCode.PROFILE_MISMATCH, AutomationCustodyCode.UNAVAILABLE, RefusalCode.INVALID_FRAME]
)
def test_a_refusal_that_is_not_an_invalid_request_cannot_carry_faults(
    code: AccessDenialCode | AutomationCustodyCode | RefusalCode,
) -> None:
    with pytest.raises(ValidationError, match="only an invalid request carries request faults"):
        _refusal(code, _FAULT)


def test_the_error_keeps_faults_for_an_invalid_request_and_refuses_them_for_any_other() -> None:
    invalid = AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=(_FAULT,))

    assert (invalid.reason, invalid.request_faults) == (AutomationCustodyCode.INVALID, (_FAULT,))
    assert AutomationCustodyError(AutomationCustodyCode.CONFLICT).request_faults == ()
    with pytest.raises(ValueError, match="only an invalid request carries request faults"):
        AutomationCustodyError(AutomationCustodyCode.CONFLICT, request_faults=(_FAULT,))
