"""The runtime selects the profile a person signs in to, and answers which one that is.

The runtime, the profile worker and its KDF child are real; only the native
login observation is a test port. No frontend writes the selection.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.bucket_pointer import pointer_path, read_pointer_selection
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.profile_access import ProfileLogin, ProfileStatus
from cadrumo_client.contracts.profile_selection import ActiveProfileReply, ActiveProfileRequest
from cadrumo_client.contracts.sign_in import SignInPresence
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
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _sign_in(connection: VerifiedConnection, profile_id: UUID) -> object:
    """Sign the person in to ``profile_id`` as ``config login`` does, keeping a sign-in for later commands."""
    secret = bytearray(PROFILE_INPUT.encode())
    request = ProfileLogin(
        request_id=uuid4(),
        profile_id=profile_id,
        method="password",
        frontend=OperationFrontendProjection.CLI,
        persist_receipt=True,
    )
    try:
        return connection.login(request, secret, deadline=time.monotonic() + 75)
    finally:
        connection.close()


def test_a_person_sign_in_selects_its_profile_in_the_runtime(tmp_path: Path) -> None:
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
        pointer_path(root).unlink(missing_ok=True)
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
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(server.serve)
            try:
                assert server.ready.wait(30)
                connection = connect(endpoint)
                try:
                    before = connection.active_profile(
                        ActiveProfileRequest(request_id=uuid4()), deadline=exchange_deadline()
                    )
                    per_command = login(connection, profile_id, "password", PROFILE_INPUT.encode())
                    unmoved = read_pointer_selection(root)
                    admitted = _sign_in(connect(endpoint), profile_id)
                    written = read_pointer_selection(root)
                    after = connection.active_profile(
                        ActiveProfileRequest(request_id=uuid4()), deadline=exchange_deadline()
                    )
                finally:
                    connection.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()

    assert isinstance(before, ActiveProfileReply) and isinstance(after, ActiveProfileReply)
    assert (before.selected_profile_id, before.presence) == (None, SignInPresence.ABSENT)
    assert isinstance(per_command, ProfileStatus) and per_command.status.denial is None
    # Authentication supplied to one command signs in without moving the selection.
    assert unmoved.bucket_id is None
    assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None
    # The runtime wrote the selection as it admitted the person's sign-in.
    assert written.bucket_id == str(profile_id)
    assert after.selected_profile_id == profile_id
