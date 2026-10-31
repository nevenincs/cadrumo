"""A wrong password is refused as ``credential_rejected`` in the sign-in refusal set, and counts toward the throttle.

The runtime, the profile worker and its KDF child are real; only the native
login observation is a test port.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from .served_runtime import connect_verified, serving_runtime
from .test_profile_connections import LoginObservation, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_a_wrong_password_is_rejected_as_a_sign_in_reason_and_throttles_the_next_attempt(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        observation = LoginObservation(owner_id())
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: observation,
            secret_store=lambda: subject.native,
            ready_seconds=30,
        ):
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
