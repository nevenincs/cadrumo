"""A first contract that composes the worker's registry leaves the profile's other requests answered.

The runtime, its profile fence, the native transport and the profile worker
are real. The test holds the runtime's call into the worker's description at
its start, as a cold composition holds it, until another session of the same
profile has read its status: with the fence held through the description that
read could only be answered after the description returned.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.profile_worker_operation_client import ProfileWorkerOperationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.runtime.deadline_budget import exchange_deadline
from cadrumo.application.runtime.operation_access import RuntimeOperationContract, RuntimeOperationContractReply
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus, RuntimeSessionRequest

from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_DESCRIPTION_HELD_SECONDS = 60
"""How long the held description waits for the status read before it proceeds regardless."""


def test_a_status_read_is_answered_while_a_first_contract_is_described(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, proceed = Event(), Event()
    describe = ProfileWorkerOperationClient.describe

    def held_describe(
        client: ProfileWorkerOperationClient, session_id: UUID, definition_id: str
    ) -> OperationPublicDefinitionDescriptionV1:
        entered.set()
        proceed.wait(_DESCRIPTION_HELD_SECONDS)
        return describe(client, session_id, definition_id)

    monkeypatch.setattr(ProfileWorkerOperationClient, "describe", held_describe)
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
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
                assert server.ready.wait(30)
                first, second = connect(endpoint), connect(endpoint)
                try:
                    sessions: list[UUID] = []
                    for client in (first, second):
                        admitted = login(client, profile_id, "password", PROFILE_INPUT.encode())
                        assert isinstance(admitted, RuntimeProfileStatus), admitted
                        assert admitted.status.session_id is not None
                        sessions.append(admitted.status.session_id)
                    contract = pool.submit(
                        first.operation,
                        RuntimeOperationContract(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=sessions[0],
                            definition_id="user-profile.field-mutation",
                        ),
                        deadline=exchange_deadline(),
                    )
                    try:
                        assert entered.wait(_DESCRIPTION_HELD_SECONDS)
                        status = second.session(
                            RuntimeSessionRequest(
                                action="session_status",
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=sessions[1],
                            ),
                            deadline=exchange_deadline(),
                        )
                        # Answered while the description is still held, not after it.
                        assert not contract.done()
                    finally:
                        proceed.set()
                    assert isinstance(status, RuntimeProfileStatus), status
                    assert status.status.session_id == sessions[1] and status.status.denial is None
                    assert isinstance(contract.result(timeout=150), RuntimeOperationContractReply)
                finally:
                    first.close()
                    second.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()
