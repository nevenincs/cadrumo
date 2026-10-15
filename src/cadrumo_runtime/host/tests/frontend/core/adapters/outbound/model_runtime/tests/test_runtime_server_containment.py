"""Where a runtime server started by the adapter lives, depending on who started it.

The adapter starts the server detached so that it outlives the process that
asked for it. A profile worker runs inside a kill-on-close job that admits no
breakaway, and detachment does not leave a job: these tests start the real
adapter's child from a real process, once free and once inside the worker's
real containment scope, and observe the child across the launcher's exit and
the scope's termination. The last ones have a contained worker ask its owner
over the real authorization channel instead, and observe the server outside
the scope and alive after it ends.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.outbound.model_runtime.process_control import spawn_runtime_server
from cadrumo.application.local_reader_contracts import LOCAL_READER_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.provisioning_host import launch_runtime_server
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
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.time.clock import now
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.adapters.tests.process_support import fixture_arguments, fixture_environment, native_python
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.adapters.tests.worker_completion import wait_file, wait_process
from cadrumo_runtime.adapters.windows_process import WindowsProcessScope
from cadrumo_runtime.adapters.worker_authorization import WorkerAuthorizationServer
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo_runtime.contracts.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest

from .runtime_server_owner_start_fixture import Seed
from .runtime_server_spawn_fixture import SERVER_SCRIPT, SERVER_SCRIPT_NAME

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires a native Windows job"),
]

_FIXTURE = "cadrumo_runtime.host.tests.frontend.core.adapters.outbound.model_runtime.tests.runtime_server_spawn_fixture"
_OWNER_START_FIXTURE = (
    "cadrumo_runtime.host.tests.frontend.core.adapters.outbound.model_runtime.tests.runtime_server_owner_start_fixture"
)
_SYNCHRONIZE_QUERY_TERMINATE = 0x100000 | 0x1000 | 0x0001


def _server_pid(record: Path) -> int:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if record.is_file() and record.stat().st_size:
            return int(json.loads(record.read_text(encoding="utf-8"))["server"])
        time.sleep(0.05)
    raise AssertionError("the launcher never recorded the server it started")


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / SERVER_SCRIPT_NAME).write_text(SERVER_SCRIPT, encoding="utf-8")
    return tmp_path / "started.json"


def test_a_server_started_by_a_free_process_outlives_it(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("requires a native Windows job")
    import win32api
    import win32event

    record = _workspace(tmp_path)
    launcher = run_audited_process(
        [str(native_python()), *fixture_arguments(_FIXTURE, str(record))],
        cwd=tmp_path,
        env=fixture_environment(),
        capture_output=True,
        timeout=60,
    )
    assert launcher.returncode == 0, launcher.stderr
    server = win32api.OpenProcess(_SYNCHRONIZE_QUERY_TERMINATE, False, _server_pid(record))
    try:
        assert win32event.WaitForSingleObject(server, 1000) == win32event.WAIT_TIMEOUT, (
            "the detached server ended with the process that started it"
        )
    finally:
        win32api.TerminateProcess(server, 1)
        win32event.WaitForSingleObject(server, 5000)
        win32api.CloseHandle(server)


def test_a_server_started_inside_a_worker_scope_is_contained_by_it_and_ends_with_it(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("requires a native Windows job")
    import win32api
    import win32event

    record = _workspace(tmp_path)
    scope = WindowsProcessScope()
    handles: list[int] = []
    try:
        launcher = scope.launch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, str(record)),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        assert launcher.wait(timeout=60) == 0
        pid = _server_pid(record)
        server = win32api.OpenProcess(_SYNCHRONIZE_QUERY_TERMINATE, False, pid)
        handles.append(server)
        assert win32event.WaitForSingleObject(server, 1000) == win32event.WAIT_TIMEOUT, (
            "the server outlives the worker process that started it, as detachment intends"
        )
        assert pid in scope.active_process_ids(), "detachment does not take the server out of the worker's job"
        scope.terminate()
        assert win32event.WaitForSingleObject(server, 5000) == win32event.WAIT_OBJECT_0, (
            "ending the worker's scope left its server running"
        )
    finally:
        scope.terminate()
        for handle in handles:
            if win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT:
                win32api.TerminateProcess(handle, 1)
            win32api.CloseHandle(handle)


class _SessionAuthority:
    """Grant the one seeded COMMIT request; session policy is not what these tests are about."""

    def __init__(self, seed: Seed) -> None:
        self.seed = seed
        self.grants = 0

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest) or request != self.seed.request:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self.grants += 1
        yield AccessAllowed(
            profile_id=request.request.profile_id,
            session_id=request.session_id,
            expires_at=now() + timedelta(seconds=25),
        )

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


def _seed(definition_id: str) -> Seed:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(), installation_id=uuid4(), os_owner_id=owner_id(), custody_generation=1, dek_epoch=uuid4()
        ),
    )
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
            definition_contract_digest="c" * 64,
            actions=frozenset({AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=False,
        ),
    )
    return Seed(identity=identity, request=request, parent_pid=os.getpid())


def test_a_contained_worker_that_asks_its_owner_gets_a_server_outside_its_scope_that_outlives_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "win32":
        pytest.skip("requires a native Windows job")
    import win32api
    import win32event

    _workspace(tmp_path)
    # The owner starts ``<executable> serve`` from its own working directory.
    monkeypatch.chdir(tmp_path)
    seed = _seed(LOCAL_READER_OPERATION_DEFINITION_ID)
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage", cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"
    ):
        settings = load_settings()
    started_by_owner: list[int | None] = []

    def start_from_owner() -> int | None:
        process_id = launch_runtime_server(
            settings, spawn=spawn_runtime_server, which=lambda _name: str(native_python())
        )
        started_by_owner.append(process_id)
        return process_id

    scope = WindowsProcessScope()
    servers: list[WorkerAuthorizationServer] = []
    handles: list[int] = []
    try:
        worker = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", _OWNER_START_FIXTURE, str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        wait_file(tmp_path / "worker.pid", worker)
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        authority = _SessionAuthority(seed)
        server = WorkerAuthorizationServer(
            identity=seed.identity,
            root=tmp_path,
            process_id=worker_pid,
            owns_process=lambda pid: pid in scope.active_process_ids(),
            contain=scope.terminate,
            owner=authority,
            runtime_server_starter=start_from_owner,
        )
        servers.append(server)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        assert wait_process(worker) == 0, (tmp_path / "failure").read_text(encoding="ascii")
        answered = json.loads((tmp_path / "started.json").read_text(encoding="utf-8"))["server"]
        assert started_by_owner == [answered], "the worker is told the process its owner started, once"
        assert isinstance(answered, int)
        assert authority.grants == 1, "the start ran under one held COMMIT fence"
        handle = win32api.OpenProcess(_SYNCHRONIZE_QUERY_TERMINATE, False, answered)
        handles.append(handle)
        assert answered not in scope.active_process_ids(), "the server its owner started is outside the worker's job"
        server.require_healthy()
        scope.terminate()
        assert win32event.WaitForSingleObject(handle, 1500) == win32event.WAIT_TIMEOUT, (
            "ending the worker's scope ended the server its owner started"
        )
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle(timeout=6)
        for handle in handles:
            if win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT:
                win32api.TerminateProcess(handle, 1)
            win32api.CloseHandle(handle)


def test_the_owner_starts_nothing_for_a_fence_held_by_another_operation(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("requires a native Windows job")
    seed = _seed("ledger.list")
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    started_by_owner: list[int] = []

    def start_from_owner() -> int | None:
        started_by_owner.append(1)
        return None

    scope = WindowsProcessScope()
    servers: list[WorkerAuthorizationServer] = []
    try:
        worker = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", _OWNER_START_FIXTURE, str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        wait_file(tmp_path / "worker.pid", worker)
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        server = WorkerAuthorizationServer(
            identity=seed.identity,
            root=tmp_path,
            process_id=worker_pid,
            owns_process=lambda pid: pid in scope.active_process_ids(),
            contain=scope.terminate,
            owner=_SessionAuthority(seed),
            runtime_server_starter=start_from_owner,
        )
        servers.append(server)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        assert wait_process(worker) == 6, "the lease the worker holds refuses to send the instruction"
        assert (tmp_path / "failure").read_text(encoding="ascii") == "RefusalError"
        assert started_by_owner == []
        assert not (tmp_path / "started.json").exists()
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle(timeout=6)
