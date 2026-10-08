"""Native process/channel fencing; application grant policy is an explicit test port."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from concurrent.futures import Future
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Event, RLock
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import (
    AUTHORITY_SECTION_MAXIMUM_SECONDS,
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.core.time.clock import now

from ..windows_process import WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from .profile_worker_support import owner_id
from .worker_authorization_fixture import Seed

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native job/pipe effect fencing"),
]


class Authority:
    def __init__(self, seed: Seed, scope: WindowsProcessScope, root: Path, process_handle: int) -> None:
        self.seed, self.scope = seed, scope
        self.lock = RLock()
        self.exited = Event()
        self.completion: Future[None] = Future()
        self.process_handle = process_handle
        self.members_at_exit: tuple[int, ...] | None = None
        self.root = root

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        assert request == self.seed.request
        with self.lock:
            if self.seed.mode == "deny":
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            if self.seed.mode == "cancel":
                (self.root / "authorizing").write_text("1", encoding="ascii")
                wait_file(self.root / "grant", self.process_handle)
            try:
                yield AccessAllowed(
                    profile_id=request.request.profile_id,
                    session_id=request.session_id,
                    expires_at=now()
                    + timedelta(seconds=3 if self.seed.mode == "expire" else AUTHORITY_SECTION_MAXIMUM_SECONDS),
                )
            finally:
                try:
                    self.members_at_exit = self.scope.active_process_ids()
                    self.exited.set()
                except BaseException as error:
                    self.completion.set_exception(error)
                    raise
                else:
                    self.completion.set_result(None)

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def wait_file(path: Path, process_handle: int) -> None:
    """Wait for a fixture marker while retaining the exact native child's outcome."""
    import win32event
    import win32process

    while not path.exists():
        refusal = path.parent / "refusal"
        assert not refusal.exists(), refusal.read_text(encoding="ascii")
        completion = win32event.WaitForSingleObject(process_handle, 0)
        assert completion in {win32event.WAIT_OBJECT_0, win32event.WAIT_TIMEOUT}
        if completion == win32event.WAIT_OBJECT_0:
            assert path.exists(), (path.name, win32process.GetExitCodeProcess(process_handle) & 0xFFFFFFFF)
        time.sleep(0.01)


def wait_process(process_handle: int) -> int:
    """Read the exact retained native child's result without a completion cap."""
    import win32event
    import win32process

    assert win32event.WaitForSingleObject(process_handle, win32event.INFINITE) == win32event.WAIT_OBJECT_0
    return win32process.GetExitCodeProcess(process_handle) & 0xFFFFFFFF


@pytest.mark.parametrize("mode", ["release", "disconnect", "expire", "deny", "cancel"])
def test_native_worker_fence_release_loss_and_expiry(
    tmp_path: Path, mode: Literal["release", "disconnect", "expire", "deny", "cancel"]
) -> None:
    import win32api
    import win32event

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
            action=AccessAction.COMMIT,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest="b" * 64,
            actions=frozenset({AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )
    seed = Seed(identity=identity, request=request, parent_pid=os.getpid(), mode=mode)
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    scope = WindowsProcessScope()
    servers: list[WorkerAuthorizationServer] = []
    handles: list[int] = []
    try:
        process = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo.adapters.local_runtime.tests.worker_authorization_fixture", str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        process_handle = win32api.OpenProcess(0x100000 | 0x1000, False, process.pid)
        handles.append(process_handle)
        assert process.pid in scope.active_process_ids()
        wait_file(tmp_path / "worker.pid", process_handle)
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        assert worker_pid in scope.active_process_ids()
        process_handle = win32api.OpenProcess(0x100000 | 0x1000, False, worker_pid)
        handles.append(process_handle)
        authority = Authority(seed, scope, tmp_path, process_handle)
        server = WorkerAuthorizationServer(
            identity=identity,
            root=tmp_path,
            process_id=worker_pid,
            owns_process=lambda pid: pid in scope.active_process_ids(),
            contain=scope.terminate,
            owner=authority,
        )
        servers.append(server)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        if mode == "deny":
            assert wait_process(process_handle) == 0, (tmp_path / "refusal").read_text(encoding="ascii")
            assert (tmp_path / "denied").is_file() and not (tmp_path / "inside").exists()
        elif mode == "cancel":
            assert wait_process(process_handle) == 0
            assert (tmp_path / "cancelled").is_file() and not (tmp_path / "inside").exists()
            authority.completion.result()
            assert authority.exited.is_set()
        else:
            wait_file(tmp_path / "inside", process_handle)
            descendant = int((tmp_path / "descendant").read_text(encoding="ascii"))
            assert descendant in scope.active_process_ids()
            handles.append(win32api.OpenProcess(0x100000, False, descendant))
            if mode != "expire":
                (tmp_path / "release").write_text("1", encoding="ascii")
            authority.completion.result()
            assert authority.exited.wait()
            if mode in {"disconnect", "expire"}:
                assert authority.members_at_exit == ()
            else:
                wait_file(tmp_path / "done", process_handle)
            for handle in handles:
                assert win32event.WaitForSingleObject(handle, win32event.INFINITE) == win32event.WAIT_OBJECT_0
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle()
        for handle in handles:
            win32api.CloseHandle(handle)
