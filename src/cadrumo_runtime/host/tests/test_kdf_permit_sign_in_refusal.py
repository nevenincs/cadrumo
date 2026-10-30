"""A sign-in queued behind the installation's KDF permit ends with its caller, and the worker serves on.

The runtime, the profile worker, its KDF child and the installation's one KDF
permit are real. Another derivation holds the permit while a second sign-in
waits for it within its caller's budget; only the native login observation is
a test port.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.kdf_supervision import profile_kdf_lease
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.profile_access import ProfileStatus, SessionRequest
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
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_QUEUED_SIGN_IN_SECONDS = 5.0
"""The caller's budget for a sign-in that cannot reach the permit while another derivation holds it."""


def test_a_sign_in_queued_for_a_taken_kdf_permit_ends_with_its_caller_and_leaves_the_worker_serving(
    tmp_path: Path,
) -> None:
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
        stop, boot = Event(), uuid4()
        observation = LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: observation,
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            serving = pool.submit(server.serve)
            try:
                assert server.ready.wait(30)
                first, second = connect(endpoint), connect(endpoint)
                clients = [first, second]
                try:
                    admitted = login(first, profile_id, "password", PROFILE_INPUT.encode())
                    assert isinstance(admitted, ProfileStatus), admitted
                    first_session = admitted.status.session_id
                    assert first_session is not None
                    held, release = Event(), Event()

                    def hold_permit() -> None:
                        with (
                            override_settings(cadrumo_storage_root=root),
                            profile_kdf_lease(deadline=time.monotonic() + 30),
                        ):
                            held.set()
                            release.wait(60)

                    holding = pool.submit(copy_context().run, hold_permit)
                    try:
                        assert held.wait(30)
                        # The worker's unwrap waits for the permit within the caller's budget; the caller
                        # running out of it is a timeout, never a wrong password.
                        with pytest.raises(RefusalError) as queued:
                            login(
                                second, profile_id, "password", PROFILE_INPUT.encode(), seconds=_QUEUED_SIGN_IN_SECONDS
                            )
                        assert queued.value.reason is RefusalCode.TIMEOUT
                    finally:
                        release.set()
                        holding.result(timeout=30)
                    # The worker still holds the first person's session: it did not end with the refusal.
                    status = first.session(
                        SessionRequest(
                            action="session_status",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=first_session,
                        ),
                        deadline=exchange_deadline(),
                    )
                    assert isinstance(status, ProfileStatus), status
                    assert status.status.session_id == first_session and status.status.denial is None
                    # With the permit free again, the same password signs in on a new connection.
                    retry = connect(endpoint)
                    clients.append(retry)
                    again = login(retry, profile_id, "password", PROFILE_INPUT.encode())
                    assert isinstance(again, ProfileStatus), again
                    assert again.status.denial is None and again.status.session_id is not None
                finally:
                    for client in clients:
                        client.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()
