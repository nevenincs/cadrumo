"""Real password admission remains independent of optional native acquisition.

OS login observations and native-store acquisition failures are explicit test
controls. Transport, encrypted profile authentication and worker custody are real;
these checks do not prove native Credential Manager or installed POSIX admission.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.automation_crypto import generate_api_key
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, Availability
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo_client.contracts.enrollment_access import EnrollmentPrepare
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers and transport"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("refusal", [AutomationCustodyCode.UNSUPPORTED, AutomationCustodyCode.UNAVAILABLE])
def test_optional_store_acquisition_cannot_block_password_or_admit_automation(
    tmp_path: Path, refusal: AutomationCustodyCode
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )

    def unavailable_store() -> AutomationSecretStore:
        raise AutomationCustodyError(refusal)

    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=unavailable_store,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[VerifiedConnection] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                while not server.ready.wait(0.01):
                    if running.done():
                        running.result()
                        pytest.fail("runtime stopped before readiness")
                human = connect(endpoint)
                clients.append(human)
                admitted = login(human, profile_id, "password", PROFILE_INPUT.encode())
                assert isinstance(admitted, ProfileStatus), admitted
                assert admitted.status.denial is None
                assert admitted.status.credential_authenticated and admitted.status.profile_bound
                assert admitted.status.profile_id == profile_id
                assert admitted.status.storage is Availability.AVAILABLE
                assert admitted.status.automation_custody is Availability.UNAVAILABLE
                session_id = admitted.status.session_id
                assert session_id is not None

                wrong_password = connect(endpoint)
                clients.append(wrong_password)
                rejected = login(wrong_password, profile_id, "password", b"invalid-synthetic-password")
                assert isinstance(rejected, AccessRefusal), rejected
                assert rejected.code in {
                    AutomationCustodyCode.CREDENTIAL_REJECTED,
                    AccessDenialCode.AUTHENTICATION_REQUIRED,
                }

                api = connect(endpoint)
                clients.append(api)
                _, credential = generate_api_key()
                api_refused = login(api, profile_id, "api_key", credential.get_secret_value())
                assert isinstance(api_refused, AccessRefusal), api_refused
                assert api_refused.code is refusal

                requester = connect(endpoint)
                clients.append(requester)
                enrollment_refused = requester.enrollment_prepare(
                    EnrollmentPrepare(
                        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(enrollment_refused, AccessRefusal), enrollment_refused
                assert enrollment_refused.code is refusal

                current = human.session(
                    SessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile_id, session_id=session_id
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(current, ProfileStatus), current
                assert current.status.denial is None and current.status.session_id == session_id
                assert current.status.automation_custody is Availability.UNAVAILABLE
            finally:
                try:
                    for client in clients:
                        client.close()
                finally:
                    stop.set()
                    try:
                        running.result()
                    finally:
                        endpoint.close()
