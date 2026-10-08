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

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_crypto import generate_api_key
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepare
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus, RuntimeSessionRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, Availability
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.tests.test_profile_connections import LoginObservation, connect, login

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

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
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )

    def unavailable_store() -> AutomationSecretStore:
        raise AutomationCustodyError(refusal)

    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
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
        clients: list[VerifiedRuntimeConnection] = []
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
                assert isinstance(admitted, RuntimeProfileStatus), admitted
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
                assert isinstance(rejected, RuntimeAccessRefusal), rejected
                assert rejected.code in {
                    AutomationCustodyCode.CREDENTIAL_REJECTED,
                    AccessDenialCode.AUTHENTICATION_REQUIRED,
                }

                api = connect(endpoint)
                clients.append(api)
                _, credential = generate_api_key()
                api_refused = login(api, profile_id, "api_key", credential.get_secret_value())
                assert isinstance(api_refused, RuntimeAccessRefusal), api_refused
                assert api_refused.code is refusal

                requester = connect(endpoint)
                clients.append(requester)
                enrollment_refused = requester.enrollment_prepare(
                    RuntimeEnrollmentPrepare(
                        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.MCP
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(enrollment_refused, RuntimeAccessRefusal), enrollment_refused
                assert enrollment_refused.code is refusal

                current = human.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile_id, session_id=session_id
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(current, RuntimeProfileStatus), current
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
