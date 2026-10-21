"""A person's sign-in that runs out of KDF time leaves the runtime ready for the retry.

A real runtime admits a real profile worker. While the installation's one KDF
permit is held by another process, the worker's password unwrap waits out its
whole budget and is refused as unavailable. The case then releases the permit
and signs in again on the same connection, reads that session's status, and
lists the profiles. None of these may wait on anything the refused attempt
left behind.
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.kdf_supervision import profile_kdf_lease
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.profile_summary import profile_listing
from cadrumo.core.config import Settings
from cadrumo_client.contracts.profile_access import ProfileStatus, SessionRequest
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_a_refused_kdf_timeout_leaves_the_retry_status_and_listing_unblocked(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile = targets[0][0].binding.profile_id
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        held, release = threading.Event(), threading.Event()

        def hold_permit() -> None:
            # The same OS-released permit the worker's unwrap must take.
            with profile_kdf_lease(settings=Settings(cadrumo_local_storage_root=root), deadline=time.monotonic() + 30):
                held.set()
                release.wait()

        holder = threading.Thread(target=hold_permit, name="kdf-permit-holder", daemon=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            clients: list[VerifiedConnection] = []
            try:
                assert server.ready.wait(3)
                human = connect(endpoint)
                clients.append(human)
                holder.start()
                assert held.wait(30)
                refused = login(human, profile, "password", PROFILE_INPUT.encode())
                assert not (isinstance(refused, ProfileStatus) and refused.status.session_id is not None), refused
                release.set()
                holder.join(timeout=30)
                assert not holder.is_alive()

                admitted = login(human, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(admitted, ProfileStatus), admitted
                assert admitted.status.denial is None, admitted
                session_id = admitted.status.session_id
                assert session_id is not None
                status = human.session(
                    SessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(status, ProfileStatus) and status.status.denial is None, status

                listing = profile_listing(root=root)
                assert listing.inventory.recognized, listing.inventory.detail
                assert {str(summary.profile_id) for summary in listing.inventory.summaries} == {
                    str(identity.binding.profile_id) for identity, _ in targets
                }
            finally:
                release.set()
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=30)
                endpoint.close()
