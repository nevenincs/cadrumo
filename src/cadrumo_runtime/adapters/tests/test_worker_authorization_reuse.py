"""Reused worker authorization connections, over real native channels to a contained child worker.

Each exchange is admitted afresh by the runtime owner port; the tests prove
what a connection may carry between exchanges and when it must close.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Lock, RLock
from typing import override
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.model_runs import ModelRunOutcome, ModelRunServed
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerModelRun,
)
from cadrumo_runtime.contracts.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest

from ..windows_process import WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from ..worker_transport import WorkerChannel
from .profile_worker_support import owner_id
from .worker_authorization_reuse_fixture import Mode, ReuseSeed

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native job/pipe effect fencing"),
]

_SERVED = ModelRunServed(provider_id="example", transport="cli", model="example-model-1", agent_version="1")


class Owner:
    """Runtime owner port: admits each exchange from what the test has set, and records what it admitted."""

    def __init__(self, root: Path, seed: ReuseSeed) -> None:
        self.root, self.seed = root, seed
        self.fence = RLock()
        self.signed_out = False
        self.admitted: list[AccessAction] = []
        self.advanced: list[tuple[str, ...]] = []
        self.model_runs = 0

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        with self.fence:
            if request.session_id == self.seed.paused_session:
                (self.root / "authorizing").write_text("1", encoding="ascii")
                _wait(self.root / "grant")
            if self.signed_out or request.session_id == self.seed.denied_session:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            self.admitted.append(request.request.action)
            yield AccessAllowed(
                profile_id=request.request.profile_id,
                session_id=request.session_id,
                expires_at=now() + timedelta(seconds=300),
            )

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
        self.model_runs += 1
        if self.seed.mode == "timeout":
            # Answered after the worker stopped waiting for it.
            time.sleep(3)
            return ModelRunOutcome(served=_SERVED, text_byte_count=4), bytearray(b"late")
        # More reply text than the result announced: the worker stops partway through the secret.
        return ModelRunOutcome(served=_SERVED, text_byte_count=4), bytearray(b"overlong")


_ACCEPTED_GUARD = Lock()


class CountingServer(WorkerAuthorizationServer):
    """The production server, counting the connections it verified."""

    accepted = 0

    @override
    def _verify_worker_channel(self, channel: WorkerChannel) -> None:
        with _ACCEPTED_GUARD:
            self.accepted += 1
        super()._verify_worker_channel(channel)


def _wait(path: Path, process_handle: int | None = None, timeout: float = 120.0) -> None:
    """Wait for a marker while noticing a child that ended without writing it."""
    import win32event

    deadline = time.monotonic() + timeout
    while not path.exists():
        if process_handle is not None and win32event.WaitForSingleObject(process_handle, 0) == win32event.WAIT_OBJECT_0:
            assert path.exists(), f"child ended before {path.name}"
        assert time.monotonic() < deadline, f"no {path.name}"
        time.sleep(0.01)


def _exit_code(process_handle: int) -> int:
    import win32event
    import win32process

    assert win32event.WaitForSingleObject(process_handle, 120_000) == win32event.WAIT_OBJECT_0
    return win32process.GetExitCodeProcess(process_handle) & 0xFFFFFFFF


def _seed(mode: Mode) -> ReuseSeed:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(), installation_id=uuid4(), os_owner_id=owner_id(), custody_generation=1, dek_epoch=uuid4()
        ),
    )
    definition_id = "user-profile.field-mutation"
    request = WorkerAuthorizationRequest(
        request_id=uuid4(),
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        request=OperationAccessRequest(
            profile_id=identity.binding.profile_id,
            definition_id=definition_id,
            action=AccessAction.START,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest="b" * 64,
            actions=frozenset({AccessAction.START, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )
    return ReuseSeed(
        identity=identity,
        request=request,
        parent_pid=os.getpid(),
        mode=mode,
        denied_session=uuid4(),
        paused_session=uuid4(),
    )


class Harness:
    def __init__(self, root: Path, owner: Owner, server: CountingServer, handle: int, scope: WindowsProcessScope):
        self.root, self.owner, self.server, self.handle, self.scope = root, owner, server, handle, scope
        self.contained = 0

    def wait(self, name: str) -> str:
        _wait(self.root / name, self.handle)
        return (self.root / name).read_text(encoding="ascii")

    def signal(self, name: str) -> None:
        (self.root / name).write_text("1", encoding="ascii")

    def opened(self) -> int:
        return int(self.wait("opened"))


@contextmanager
def _worker(tmp_path: Path, mode: Mode, *, owns: list[bool] | None = None) -> Generator[Harness]:
    """Run the fixture worker in an owned job against a production server in this process."""
    import win32api

    seed = _seed(mode)
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    scope = WindowsProcessScope()
    owner = Owner(tmp_path, seed)
    owned = owns if owns is not None else [True]
    handles: list[int] = []
    servers: list[CountingServer] = []
    try:
        process = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo_runtime.adapters.tests.worker_authorization_reuse_fixture", str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        handles.append(win32api.OpenProcess(0x100000 | 0x1000, False, process.pid))
        _wait(tmp_path / "worker.pid", handles[0])
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        handle = win32api.OpenProcess(0x100000 | 0x1000, False, worker_pid)
        handles.append(handle)
        harness_box: list[Harness] = []

        def contain() -> None:
            harness_box[0].contained += 1
            scope.terminate()

        server = CountingServer(
            identity=seed.identity,
            root=tmp_path,
            process_id=worker_pid,
            owns_process=lambda pid: owned[0] and pid in scope.active_process_ids(),
            contain=contain,
            owner=owner,
        )
        servers.append(server)
        harness = Harness(tmp_path, owner, server, handle, scope)
        harness_box.append(harness)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        yield harness
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle()
        for handle in handles:
            win32api.CloseHandle(handle)


def test_one_connection_serves_every_clean_exchange_each_admitted_afresh(tmp_path: Path) -> None:
    """Two permits, a check and a progress report share one verified connection, each admitted on arrival."""
    with _worker(tmp_path, "reuse") as worker:
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 0
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START, AccessAction.START, AccessAction.START]
        assert worker.owner.advanced == [("c" * 64,)]
        assert worker.contained == 0
        worker.server.require_healthy()


def test_a_check_refuses_on_failed_admission_and_an_allowed_check_holds_no_fence(tmp_path: Path) -> None:
    with _worker(tmp_path, "check") as worker:
        assert worker.wait("check_refused") == "access:session_inactive"
        # A COMMIT permit keeps the owner's fence on the runtime thread while its body runs.
        worker.wait("commit_held")
        assert not worker.owner.fence.acquire(blocking=False)
        worker.signal("commit_probed")
        # An allowed check has been answered with nothing held.
        worker.wait("checked")
        assert worker.owner.fence.acquire(blocking=False)
        worker.owner.fence.release()
        worker.signal("check_probed")
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 0
        assert worker.owner.admitted == [AccessAction.START, AccessAction.COMMIT, AccessAction.START]
        # The refused check left the connection reusable: one connection served all four exchanges.
        assert worker.server.accepted == 1
        assert worker.contained == 0


def test_a_revocation_between_two_exchanges_on_one_connection_refuses_the_second(tmp_path: Path) -> None:
    with _worker(tmp_path, "revoke") as worker:
        worker.wait("first")
        worker.owner.signed_out = True
        worker.signal("revoked")
        assert worker.wait("second") == "access:session_inactive"
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 0
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START]


@pytest.mark.parametrize(
    ("mode", "refusal"),
    [
        ("frame", "refusal:runtime_connection_closed"),
        ("timeout", "refusal:runtime_deadline_exceeded"),
        ("secret", "refusal:runtime_invalid_frame"),
    ],
)
def test_a_faulted_exchange_closes_its_connection_without_containing_the_worker(
    tmp_path: Path, mode: Mode, refusal: str
) -> None:
    """A clean exchange, then a faulted one on the same connection, then a fresh connection for the next."""
    with _worker(tmp_path, mode) as worker:
        assert worker.wait("fault") == refusal
        assert worker.opened() == 2
        assert _exit_code(worker.handle) == 0
        assert worker.server.accepted == 2
        assert worker.contained == 0
        worker.server.require_healthy()


def test_a_cancelled_stage_releases_its_permit_and_closes_its_connection(tmp_path: Path) -> None:
    with _worker(tmp_path, "cancel") as worker:
        worker.wait("cancelled")
        assert worker.opened() == 2
        assert _exit_code(worker.handle) == 0
        assert not (tmp_path / "inside_cancelled").exists()
        assert worker.server.accepted == 2
        assert worker.contained == 0
        worker.server.require_healthy()


def test_an_incarnation_mismatch_refuses_the_next_exchange_on_a_reused_connection(tmp_path: Path) -> None:
    owns = [True]
    with _worker(tmp_path, "incarnation", owns=owns) as worker:
        worker.wait("idle")
        owns[0] = False
        worker.signal("changed")
        assert worker.wait("second").startswith("refusal:")
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 0
        # The second exchange reached the verified connection and was refused before it was read.
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START, AccessAction.START]
        assert worker.contained == 0


def test_runtime_stop_closes_idle_connections(tmp_path: Path) -> None:
    with _worker(tmp_path, "stop") as worker:
        worker.wait("idle")
        worker.server.close()
        # The idle connection's thread wakes and closes while the worker still holds its end.
        worker.server.settle(timeout=10)
        worker.signal("changed")
        assert worker.wait("second").startswith("refusal:")
        assert _exit_code(worker.handle) == 0
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START, AccessAction.START]
        assert worker.contained == 0


def test_losing_an_idle_connection_contains_nothing(tmp_path: Path) -> None:
    with _worker(tmp_path, "idle_loss") as worker:
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 0
        # The runtime notices the lost connection while it waits for the next exchange, not through a stop.
        time.sleep(1.0)
        assert worker.contained == 0
        worker.server.require_healthy()
        worker.server.close()
        worker.server.settle(timeout=10)
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START, AccessAction.START]
        assert worker.contained == 0


def test_losing_a_reused_connection_with_an_outstanding_permit_contains_the_worker(tmp_path: Path) -> None:
    with _worker(tmp_path, "permit_loss") as worker:
        assert worker.opened() == 1
        assert _exit_code(worker.handle) == 4
        deadline = time.monotonic() + 30
        while worker.contained == 0:
            assert time.monotonic() < deadline, "the lost permit was not contained"
            time.sleep(0.01)
        # The COMMIT permit was issued on the connection the first stage had already used.
        assert worker.server.accepted == 1
        assert worker.owner.admitted == [AccessAction.START, AccessAction.COMMIT]
