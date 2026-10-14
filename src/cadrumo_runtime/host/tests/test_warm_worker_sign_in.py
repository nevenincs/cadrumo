"""A second sign-in on a warm profile worker never waits for its operation registry.

The worker composes the registry, its handlers and the tax authority for the
first operation a session asks for. A second person signing in to the same
worker meanwhile is answered within the worker's own exchange budgets: it once
queued behind that composition on the worker's control channel and its binding
timed out after the 10 s control budget. The real transport enforces those
budgets, so a regression surfaces as a refused sign-in, not as a wall-clock
threshold this test would have to guess.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo_client.contracts.operation_access import OperationContract, OperationContractReply
from cadrumo_client.contracts.profile_access import ProfileStatus
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


@pytest.mark.parametrize("composing", [False, True], ids=["idle", "composing"])
def test_a_second_sign_in_is_answered_while_the_first_operation_composes(tmp_path: Path, composing: bool) -> None:
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
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            serving = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                first, second = connect(endpoint), connect(endpoint)
                try:
                    admitted = login(first, profile_id, "password", PROFILE_INPUT.encode())
                    assert isinstance(admitted, ProfileStatus)
                    session = admitted.status.session_id
                    assert session is not None
                    # The first session's first operation composes the registry,
                    # alongside the second sign-in or after it.
                    request = OperationContract(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=session,
                        definition_id="user-profile.field-mutation",
                    )
                    contract = (
                        pool.submit(first.operation, request, deadline=time.monotonic() + 75) if composing else None
                    )
                    started = time.monotonic()
                    again = login(second, profile_id, "password", PROFILE_INPUT.encode())
                    elapsed = time.monotonic() - started
                    if contract is None:
                        contract = pool.submit(first.operation, request, deadline=time.monotonic() + 75)
                    print("second_sign_in_seconds", elapsed, "composition_done", contract.done(), flush=True)

                    assert isinstance(again, ProfileStatus)
                    assert again.status.denial is None
                    assert again.status.session_id not in {None, session}
                    assert isinstance(contract.result(timeout=90), OperationContractReply)
                finally:
                    first.close()
                    second.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()
