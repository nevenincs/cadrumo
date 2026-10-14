"""A port this process failed to compose is reported as an internal failure, never as an absent runtime."""

from __future__ import annotations

import pytest

from cadrumo.application.operator_output.connection_remedies import connection_unavailable_remedy
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ..protocol_contract import refusal_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_uncomposed_port_is_an_internal_failure_with_no_runtime_remedy() -> None:
    code = refusal_code(InternalInvariantError("profile login-session infrastructure has not been composed"))

    assert code == "internal_error"
    assert connection_unavailable_remedy(code) is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value), "authentication_required"),
        (FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value), "profile_mismatch"),
        (RefusalError(RefusalCode.UNAVAILABLE), "runtime_unavailable"),
        (ConnectionResetError(), "runtime_unavailable"),
    ],
)
def test_typed_refusals_and_a_lost_connection_keep_their_codes(error: Exception, expected: str) -> None:
    assert refusal_code(error) == expected
