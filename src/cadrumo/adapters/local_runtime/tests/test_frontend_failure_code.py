"""A failed frontend exchange reports only an allowlisted public code."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import AccessDenialCode

from ..frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Strict(BaseModel):
    value: int


def _validation_error() -> ValidationError:
    try:
        _Strict.model_validate({"value": "not-a-number"})
    except ValidationError as error:
        return error
    raise AssertionError("the synthetic payload must fail validation")


def test_application_refusal_keeps_its_own_code() -> None:
    refused = RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    assert frontend_failure_code(refused) == AccessDenialCode.PROFILE_MISMATCH.value


def test_runtime_refusal_keeps_its_transport_code() -> None:
    refused = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    assert frontend_failure_code(refused) == RuntimeRefusalCode.DEADLINE_EXCEEDED.value


def test_contract_violation_is_an_invalid_frame() -> None:
    assert frontend_failure_code(_validation_error()) == RuntimeRefusalCode.INVALID_FRAME.value


def test_other_failures_hide_their_private_message() -> None:
    assert frontend_failure_code(OSError("private pipe path")) == RuntimeRefusalCode.UNAVAILABLE.value
