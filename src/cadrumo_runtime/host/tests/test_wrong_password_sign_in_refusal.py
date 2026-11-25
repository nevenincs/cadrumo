"""A wrong password is refused as ``credential_rejected`` in the sign-in refusal set, and counts toward the throttle.

The runtime, the profile worker and its KDF child are real; only the native
login observation is a test port.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.profile_access import AccessRefusal

from .served_profile_runtime import serving_enrolled_profile
from .served_runtime import connect_verified
from .test_profile_connections import login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_a_wrong_password_is_rejected_as_a_sign_in_reason_and_throttles_the_next_attempt(tmp_path: Path) -> None:
    with serving_enrolled_profile(tmp_path, ready_seconds=30) as profile:
        endpoint, profile_id = profile.endpoint, profile.profile_id
        first, second = connect_verified(endpoint), connect_verified(endpoint)
        try:
            rejected = login(first, profile_id, "password", b"not the profile password")
            assert isinstance(rejected, AccessRefusal), rejected
            assert rejected.code is AutomationCustodyCode.CREDENTIAL_REJECTED, rejected
            assert rejected.sign_in is not None and rejected.sign_in.reason == "credential_rejected"
            assert rejected.sign_in.remaining_seconds is None
            # The failure was counted before the reply: the right password is held back for its wait.
            throttled = login(second, profile_id, "password", PROFILE_INPUT.encode())
            assert isinstance(throttled, AccessRefusal), throttled
            assert throttled.code is AccessDenialCode.AUTHENTICATION_REQUIRED, throttled
            assert throttled.sign_in is not None and throttled.sign_in.reason == "throttled"
            assert throttled.sign_in.remaining_seconds is not None
            assert throttled.sign_in.remaining_seconds > 0
        finally:
            first.close()
            second.close()
