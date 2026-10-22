"""Incarnation rechecks on reused authorization channels, with a pipe that outlives its verified process.

Each test runs a real peer process that completes the real verification and
handshake, hands its pipe end to this process and exits. The pipe stays open,
so only the recheck of the retained peer handle can tell the peer is gone.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from contextlib import AbstractContextManager
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, OperationResponseScopeAllowed
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.model_runs import ModelRunOutcome
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerModelRun,
    WorkerOperationsAdvanced,
)
from cadrumo_runtime.contracts.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest

from ..windows_process import WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from ..worker_authorization_connections import WorkerAuthorizationConnections
from .profile_worker_support import owner_id
from .worker_authorization_incarnation_fixture import IncarnationSeed

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native pipe peer handles"),
]

_FIXTURE = "cadrumo_runtime.adapters.tests.worker_authorization_incarnation_fixture"


class Owner:
    """Runtime owner port that admits nothing and records any report that reaches it."""

    def __init__(self) -> None:
        self.advanced: list[tuple[str, ...]] = []

    def authorize(
        self, request: WorkerAuthorityRequest
    ) -> AbstractContextManager[AccessAllowed | OperationResponseScopeAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def operations_advanced(self, operation_ids: tuple[str, ...], *, records_changed: bool = False) -> None:
        self.advanced.append(operation_ids)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def model_run(
        self, authority: WorkerAuthorizationRequest, command: WorkerModelRun, body: bytearray
    ) -> tuple[ModelRunOutcome, bytearray]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(), installation_id=uuid4(), os_owner_id=owner_id(), custody_generation=1, dek_epoch=uuid4()
        ),
    )


def _wait(path: Path, timeout: float = 60.0) -> str:
    deadline = time.monotonic() + timeout
    while not path.exists():
        assert time.monotonic() < deadline, f"no {path.name}"
        time.sleep(0.01)
    return path.read_text(encoding="ascii")


def _wait_exit(pid: int) -> None:
    import win32api
    import win32event

    try:
        handle = win32api.OpenProcess(0x100000, False, pid)
    except Exception:
        return
    try:
        assert win32event.WaitForSingleObject(handle, 60_000) == win32event.WAIT_OBJECT_0
    finally:
        win32api.CloseHandle(handle)


@pytest.fixture
def seeded(tmp_path: Path) -> Generator[tuple[Path, ProfileWorkerIdentity]]:
    yield tmp_path, _identity()


def test_the_runtime_refuses_an_exchange_on_a_pipe_whose_verified_worker_has_ended(
    seeded: tuple[Path, ProfileWorkerIdentity],
) -> None:
    """The report arrives on the verified pipe after its worker exited; it is not read, and nothing is contained."""
    root, identity = seeded
    (root / "seed.json").write_text(
        IncarnationSeed(identity=identity, parent_pid=os.getpid(), role="worker").model_dump_json(), encoding="utf-8"
    )
    scope = WindowsProcessScope()
    owner = Owner()
    contained: list[int] = []
    servers: list[WorkerAuthorizationServer] = []
    channels: list[WindowsChannel] = []
    try:
        scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", _FIXTURE, str(root)),
            directory=root,
            environment=os.environ.copy(),
        )
        peer_pid = int(_wait(root / "peer.pid"))
        servers.append(
            WorkerAuthorizationServer(
                identity=identity,
                root=root,
                process_id=peer_pid,
                # Job membership is not what this test isolates: only the retained peer handle can refuse.
                owns_process=lambda pid: True,
                contain=lambda: contained.append(1),
                owner=owner,
            )
        )
        (root / "listening").write_text("1", encoding="ascii")
        handed = int(_wait(root / "handle"))
        _wait_exit(peer_pid)
        # This process now holds the ended worker's end of the verified pipe.
        channel = WindowsChannel(handed, server=False)
        channels.append(channel)
        write_document(
            channel,
            WorkerOperationsAdvanced(request_id=uuid4(), operation_ids=("c" * 64,)),
            deadline=time.monotonic() + 5,
        )
        with pytest.raises(RefusalError) as refused:
            read_document(channel, WorkerAuthorizationAcknowledgement, deadline=time.monotonic() + 10)
        assert refused.value.reason is RefusalCode.CONNECTION_CLOSED
        assert owner.advanced == []
        assert contained == []
        servers[0].require_healthy()
    finally:
        for channel in channels:
            channel.close()
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle()


def test_the_worker_does_not_reuse_a_connection_whose_verified_runtime_has_ended(
    seeded: tuple[Path, ProfileWorkerIdentity],
) -> None:
    """The pipe is still open after its runtime exited; only the recheck of the retained peer handle refuses it."""
    import win32api

    root, identity = seeded
    (root / "seed.json").write_text(
        IncarnationSeed(identity=identity, parent_pid=os.getpid(), role="runtime").model_dump_json(), encoding="utf-8"
    )
    (root / "listening").write_text("1", encoding="ascii")
    scope = WindowsProcessScope()
    handed: list[int] = []
    connections: list[WorkerAuthorizationConnections] = []
    try:
        scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", _FIXTURE, str(root)),
            directory=root,
            environment=os.environ.copy(),
        )
        peer_pid = int(_wait(root / "peer.pid"))
        _wait(root / "serving")
        pool = WorkerAuthorizationConnections(identity=identity, root=root, parent_pid=peer_pid)
        connections.append(pool)
        channel = pool.checkout(time.monotonic() + 10)
        pool.checkin(channel, reusable=True)
        handed.append(int(_wait(root / "handle")))
        _wait_exit(peer_pid)
        # The pipe itself stays open and quiet: its server end is held here now.
        assert not channel.read_ready()
        with pytest.raises(RefusalError):
            pool.checkout(time.monotonic() + 2)
        # The stale connection was closed, not handed out, and no other was verified.
        with pytest.raises(RefusalError):
            channel.read_ready()
        assert pool.opened == 1
    finally:
        for pool in connections:
            pool.close()
        for handle in handed:
            win32api.CloseHandle(handle)
        scope.terminate()
