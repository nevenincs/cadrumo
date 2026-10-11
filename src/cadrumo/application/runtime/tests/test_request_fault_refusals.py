"""Only a refusal of an invalid request carries the request model's faults, on the wire and in the error."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....core.request_faults import RequestFault
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..contracts import RuntimeRefusalCode
from ..profile_access import RuntimeAccessRefusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FAULT = RequestFault(location=("patch", "taxable_base"), type="value_error", message="a synthetic rule")


def _refusal(
    code: AccessDenialCode | AutomationCustodyCode | RuntimeRefusalCode, *faults: RequestFault
) -> RuntimeAccessRefusal:
    return RuntimeAccessRefusal(
        request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), code=code, request_faults=faults
    )


def test_an_invalid_refusal_carries_its_faults_through_the_wire_document() -> None:
    refusal = _refusal(AutomationCustodyCode.INVALID, _FAULT)

    read_back = RuntimeAccessRefusal.model_validate_json(refusal.model_dump_json())

    assert read_back.request_faults == (_FAULT,)
    assert read_back.request_faults[0].model_dump(mode="json") == {
        "location": ["patch", "taxable_base"],
        "type": "value_error",
        "message": "a synthetic rule",
    }


def test_a_refusal_with_no_faults_says_so() -> None:
    assert _refusal(AutomationCustodyCode.INVALID).request_faults == ()
    assert _refusal(AccessDenialCode.PROFILE_MISMATCH).request_faults == ()


@pytest.mark.parametrize(
    "code", [AccessDenialCode.PROFILE_MISMATCH, AutomationCustodyCode.UNAVAILABLE, RuntimeRefusalCode.INVALID_FRAME]
)
def test_a_refusal_that_is_not_an_invalid_request_cannot_carry_faults(
    code: AccessDenialCode | AutomationCustodyCode | RuntimeRefusalCode,
) -> None:
    with pytest.raises(ValidationError, match="only an invalid request carries request faults"):
        _refusal(code, _FAULT)


def test_the_error_keeps_faults_for_an_invalid_request_and_refuses_them_for_any_other() -> None:
    invalid = AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=(_FAULT,))

    assert (invalid.reason, invalid.request_faults) == (AutomationCustodyCode.INVALID, (_FAULT,))
    assert AutomationCustodyError(AutomationCustodyCode.CONFLICT).request_faults == ()
    with pytest.raises(ValueError, match="only an invalid request carries request faults"):
        AutomationCustodyError(AutomationCustodyCode.CONFLICT, request_faults=(_FAULT,))
