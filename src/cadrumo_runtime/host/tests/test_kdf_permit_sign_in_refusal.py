"""A sign-in that cannot get the installation's KDF permit is refused, and the worker serves on.

The runtime, the profile worker, its KDF child and the installation's one KDF
permit are real. Another derivation holds the permit past the bound of the
worker's password unwrap; only the native login observation is a test port.
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

from cadrumo.adapters.persistence.storage.custody.kdf_supervision import (
    PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
    profile_kdf_lease,
)
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
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

_HELD_PAST_THE_UNWRAP_SECONDS = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS + 10
"""Longer than the worker's password unwrap may wait for the permit, so its sign-in cannot derive."""


def test_a_sign_in_refused_for_a_taken_kdf_permit_leaves_the_worker_serving(tmp_path: Path) -> None:
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
                try:
                    admitted = login(first, profile_id, "password", PROFILE_INPUT.encode())
                    assert isinstance(admitted, ProfileStatus), admitted
                    first_session = admitted.status.session_id
                    assert first_session is not None
                    held, release = Event(), Event()

                    def hold_permit() -> None:
                        with (
                            override_settings(cadrumo_local_storage_root=root),
                            profile_kdf_lease(deadline=time.monotonic() + 30),
                        ):
                            held.set()
                            release.wait(_HELD_PAST_THE_UNWRAP_SECONDS)

                    holding = pool.submit(copy_context().run, hold_permit)
                    try:
                        assert held.wait(30)
                        refused = login(second, profile_id, "password", PROFILE_INPUT.encode())
                    finally:
                        release.set()
                        holding.result(timeout=30)
                    # Refused as unavailable for now, never as a wrong password, and on a live connection.
                    assert isinstance(refused, AccessRefusal), refused
                    assert refused.code == "unavailable", refused
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
                    # With the permit free again, the same password signs in.
                    again = login(second, profile_id, "password", PROFILE_INPUT.encode())
                    assert isinstance(again, ProfileStatus), again
                    assert again.status.denial is None and again.status.session_id is not None
                finally:
                    first.close()
                    second.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()
