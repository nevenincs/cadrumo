"""Cold human admission prepares contracts before publishing a usable session."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.operation_access import RuntimeOperationContract, RuntimeOperationContractReply
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus

from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("_attempt", range(3))
def test_cold_and_shared_human_admission_publish_ready_contracts(tmp_path: Path, _attempt: int) -> None:
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
                assert server.ready.wait(3)
                first, second = connect(endpoint), connect(endpoint)
                try:
                    sessions = []
                    for client in (first, second):
                        started = time.monotonic()
                        admitted = login(client, profile_id, "password", PROFILE_INPUT.encode())
                        print("human_admission_seconds", time.monotonic() - started, flush=True)
                        assert isinstance(admitted, RuntimeProfileStatus)
                        assert admitted.status.denial is None
                        session = admitted.status.session_id
                        assert session is not None
                        sessions.append(session)
                        contract = client.operation(
                            RuntimeOperationContract(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=session,
                                definition_id="user-profile.field-mutation",
                            ),
                            deadline=time.monotonic() + 10,
                        )
                        assert isinstance(contract, RuntimeOperationContractReply)
                    assert sessions[0] != sessions[1]
                finally:
                    first.close()
                    second.close()
            finally:
                stop.set()
                serving.result(timeout=20)
                endpoint.close()
