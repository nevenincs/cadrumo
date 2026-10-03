"""Real installed workers and synthetic encrypted profiles, without a native key store."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict, SecretBytes, TypeAdapter

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationId, OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAllowed,
    AccessDenialCode,
    AccessSession,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.bucket_pointer import read_pointer
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ..profile_worker import ProfileWorkerProcess
from .process_support import fixture_arguments, fixture_environment
from .profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def profiles(tmp_path: Path):
    with worker_profiles(tmp_path) as subjects:
        yield subjects


class _AllowWorkerOperations:
    """Permit only the operation checks exercised by this installed-worker case."""

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        yield AccessAllowed(
            profile_id=request.request.profile_id,
            session_id=request.session_id,
            expires_at=now() + timedelta(seconds=20),
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


def _login_human(profile_id: UUID) -> None:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )


def _record_snapshot(profile_id: UUID) -> tuple[int, str, dict[str, str]]:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
        return record.record_revision, record.content_digest, record_to_path_values(record)
    finally:
        close_active_bucket_session()


def _wait_for_terminal(worker: ProfileWorkerProcess, session_id: UUID, operation_id: OperationId):
    request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    deadline = time.monotonic() + 10
    while True:
        observation = worker.observe(session_id, request).observation
        assert isinstance(observation, OperationObservationSuccessV1), observation
        projection = observation.projection
        if projection.terminal_condition is not None:
            return projection
        assert time.monotonic() < deadline, f"operation {operation_id} did not settle"
        time.sleep(0.02)


def _field_request(
    profile_id: UUID, *, revision: int, digest: str, value: str, idempotency_key: str
) -> OperationRequest[ProfileFieldMutationOperationRequest]:
    return OperationRequest(
        definition_id="user-profile.field-mutation",
        subject_ref=f"profile:{profile_id}",
        payload=ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value=value,
        ),
        idempotency_key=idempotency_key,
    )


def test_concurrent_profiles_never_retarget_and_disconnect_is_isolated(profiles) -> None:
    root, ((first, first_key), (second, second_key)) = profiles
    with ExitStack() as cleanup:
        a = ProfileWorkerProcess(first, storage_root=root)
        cleanup.callback(a.close)
        b = ProfileWorkerProcess(second, storage_root=root)
        cleanup.callback(b.close)
        a_lease, b_lease = lease(first), lease(second)
        a_buffer, b_buffer = bytearray(first_key), bytearray(second_key)
        a.install(a_lease, a_buffer)
        b.install(b_lease, b_buffer)
        assert not any(a_buffer) and not any(b_buffer)
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        # A foreign profile's valid DEK cannot switch this process to B.
        with pytest.raises(AutomationCustodyError):
            a.install(b_lease, bytearray(second_key))
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        b.retire(b_lease.session_id)
        assert not b.status().sessions
        fresh = lease(second)
        b.install(fresh, bytearray(second_key))
        assert b.status().sessions == (fresh.session_id,)


def test_worker_rejects_wrong_dek_before_acknowledging_custody(profiles) -> None:
    root, ((identity, key), (_other, wrong_key)) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        secret = bytearray(wrong_key)
        with pytest.raises(AutomationCustodyError):
            worker.install(lease(identity), secret)
        assert not any(secret)
        admitted = lease(identity)
        worker.install(admitted, bytearray(key))
        assert worker.status().sessions == (admitted.session_id,)
    finally:
        worker.close()


def test_refresh_and_idle_expiry_release_only_the_affected_leases(profiles) -> None:
    root, ((identity, key), _) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        # Prepare the cold application graph before starting the expiry clock.
        worker.prepare_api_admission(deadline=time.monotonic() + 30)
        short, independent = lease(identity, seconds=2), lease(identity)
        worker.install(short, bytearray(key))
        worker.install(independent, bytearray(key))
        refreshed = changed(
            short, issued_at=now(), issued_monotonic=time.monotonic(), expires_at=now() + timedelta(seconds=4)
        )
        worker.refresh(refreshed)
        worker.retire(independent.session_id)
        assert worker.status().sessions == (short.session_id,)
        deadline = time.monotonic() + 6
        while worker.status().sessions and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not worker.status().sessions
        with pytest.raises(AutomationCustodyError):
            worker.refresh(
                changed(
                    refreshed,
                    issued_at=now(),
                    issued_monotonic=time.monotonic(),
                    expires_at=now() + timedelta(seconds=30),
                )
            )
    finally:
        worker.close()


def test_password_candidate_does_not_replace_agents_or_select_another_profile(profiles) -> None:
    root, ((identity, key), _) = profiles
    selected = read_pointer(root)
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        api = lease(identity)
        worker.install(api, bytearray(key))
        password = bytearray(PROFILE_INPUT.encode())
        with worker.authenticate_human(password) as outcome:
            assert outcome.bucket_id == str(identity.binding.profile_id) and not outcome.session_persisted
            assert worker.status().sessions == (api.session_id,)
            human = AccessSession(
                session_id=uuid4(),
                binding=identity.binding,
                profile_lock_generation=0,
                runtime_boot_id=identity.runtime_boot_id,
                connection_id=uuid4(),
                client_id=uuid4(),
                kind=SessionKind.HUMAN,
                originating_login_id="synthetic-login",
                state=SessionState.ACTIVE,
                scope=api.scope,
                issued_at=now(),
                issued_monotonic=time.monotonic(),
                expires_at=min(outcome.idle_deadline, outcome.absolute_deadline),
            )
            worker.bind_human(human)
        assert not any(password)
        assert set(worker.status().sessions) == {api.session_id, human.session_id}
        worker.retire(human.session_id)
        assert worker.status().sessions == (api.session_id,)
        wrong = bytearray(b"wrong-synthetic-worker-input")
        with pytest.raises(AutomationCustodyError), worker.authenticate_human(wrong):
            pytest.fail("incorrect password must not create a candidate")
        assert not any(wrong)
        assert worker.status().sessions == (api.session_id,)
        assert read_pointer(root) == selected
    finally:
        worker.close()


def test_simultaneous_profile_operations_survive_human_switch_and_stale_revision_conflict(profiles) -> None:
    root, ((identity_a, key_a), (identity_b, key_b)) = profiles
    baseline_a = _record_snapshot(identity_a.binding.profile_id)
    baseline_b = _record_snapshot(identity_b.binding.profile_id)
    _login_human(identity_a.binding.profile_id)
    assert read_pointer(root).bucket_id == str(identity_a.binding.profile_id)

    authority = _AllowWorkerOperations()
    with ExitStack() as cleanup:
        worker_a = ProfileWorkerProcess(identity_a, storage_root=root, authorization=authority)
        cleanup.callback(worker_a.close)
        worker_b = ProfileWorkerProcess(identity_b, storage_root=root, authorization=authority)
        cleanup.callback(worker_b.close)
        lease_a, lease_b = lease(identity_a), lease(identity_b)
        worker_a.install(lease_a, bytearray(key_a))
        worker_b.install(lease_b, bytearray(key_b))

        # A real human login changes the shared default pointer while both workers retain
        # their immutable bindings and installed custody.
        _login_human(identity_b.binding.profile_id)
        assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)

        request_a = _field_request(
            identity_a.binding.profile_id,
            revision=baseline_a[0],
            digest=baseline_a[1],
            value="es",
            idempotency_key="agent-a-language-write",
        )
        request_b = _field_request(
            identity_b.binding.profile_id,
            revision=baseline_b[0],
            digest=baseline_b[1],
            value="ca",
            idempotency_key="agent-b-language-write",
        )
        submitted_a = worker_a.submit(lease_a.session_id, request_a, frontend=OperationFrontendProjection.MCP)
        submitted_b = worker_b.submit(lease_b.session_id, request_b, frontend=OperationFrontendProjection.MCP)
        with ThreadPoolExecutor(max_workers=2) as pool:
            started = (
                pool.submit(worker_a.start, lease_a.session_id, submitted_a.receipt.operation_id),
                pool.submit(worker_b.start, lease_b.session_id, submitted_b.receipt.operation_id),
            )
            for future in started:
                future.result(timeout=10)

        result_a = _wait_for_terminal(worker_a, lease_a.session_id, submitted_a.receipt.operation_id)
        result_b = _wait_for_terminal(worker_b, lease_b.session_id, submitted_b.receipt.operation_id)
        assert result_a.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert result_b.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)

        stale_request = _field_request(
            identity_a.binding.profile_id,
            revision=baseline_a[0],
            digest=baseline_a[1],
            value="en",
            idempotency_key="agent-a-stale-language-write",
        )
        stale = worker_a.submit(lease_a.session_id, stale_request, frontend=OperationFrontendProjection.MCP)
        worker_a.start(lease_a.session_id, stale.receipt.operation_id)
        stale_result = _wait_for_terminal(worker_a, lease_a.session_id, stale.receipt.operation_id)
        assert stale_result.terminal_condition is OperationTerminalCondition.FAILED
        assert stale_result.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"

    observed_a = _record_snapshot(identity_a.binding.profile_id)
    observed_b = _record_snapshot(identity_b.binding.profile_id)
    assert observed_a[0] > baseline_a[0]
    assert observed_a[2][PROFILE_OUTPUT_LANGUAGE_PATH] == "es"
    assert observed_b[0] > baseline_b[0]
    assert observed_b[2][PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
    _login_human(identity_b.binding.profile_id)
    assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)


class _WindowsBrowserAdmission(BaseModel):
    runtime_pid: int
    worker_pid: int
    session_id: UUID
    buffer_wiped: bool


class _WindowsBrowserParent(BaseModel):
    runtime_pid: int
    created: str


class _WindowsBrowserReady(BaseModel):
    worker_pid: int
    executable: Path
    title: str


class _WindowsJobMember(BaseModel):
    pid: int
    created: str


class _WindowsBrowserFixture:
    """Keep the expendable owner and observation handles through failed assertions."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.handles: dict[int, int] = {}
        self.stderr: bytes | None = None
        self.runtime_pid: int | None = None

    async def close(self) -> None:
        import win32api
        import win32event

        if self.stderr is None:
            if self.runtime_pid is not None:
                handle = self.handles[self.runtime_pid]
                if win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT:
                    win32api.TerminateProcess(handle, 124)
            if self.process.returncode is None:
                self.process.kill()
            _, self.stderr = await asyncio.wait_for(self.process.communicate(), timeout=10)
        for pid, handle in tuple(self.handles.items()):
            win32api.CloseHandle(handle)
            del self.handles[pid]


async def _windows_fixture_record[T: BaseModel](path: Path, model: type[T], owner: _WindowsBrowserFixture) -> T:
    deadline = time.monotonic() + 35
    failure = path.parent / "windows-worker-browser-failure.json"
    while not path.exists():
        assert not failure.exists(), "post-admission browser fixture reported failure"
        assert owner.process.returncode is None, "profile worker owner exited before its browser became ready"
        assert time.monotonic() < deadline, "post-admission browser fixture did not publish its record"
        await asyncio.sleep(0.05)
    encoded = path.read_bytes()
    assert len(encoded) <= 4096
    return model.model_validate_json(encoded)


async def _windows_job_members(owner: _WindowsBrowserFixture) -> dict[int, str]:
    assert owner.process.stdin is not None and owner.process.stdout is not None
    owner.process.stdin.write(b"members\n")
    await owner.process.stdin.drain()
    encoded = await asyncio.wait_for(owner.process.stdout.readline(), timeout=5)
    assert 0 < len(encoded) <= 65536
    members = TypeAdapter(list[_WindowsJobMember]).validate_json(encoded)
    assert 4 <= len(members) <= 4096
    assert len({member.pid for member in members}) == len(members)
    assert all(member.pid > 0 for member in members)
    return {member.pid: member.created for member in members}


@pytest.mark.asyncio
async def test_admitted_worker_browser_descendants_end_on_owner_death(tmp_path: Path) -> None:
    """Real private admission precedes Chromium; native object identities prove the observed cut."""
    import psutil
    import win32api
    import win32con
    import win32event
    import win32process

    owner = _WindowsBrowserFixture(
        await asyncio.create_subprocess_exec(
            sys.executable,
            *fixture_arguments(
                "cadrumo.entrypoints.runtime.tests.windows_worker_parent_fixture",
                "admitted-browser-owner",
                str(tmp_path),
            ),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=fixture_environment(),
        )
    )
    try:
        assert owner.process.stdout is not None
        encoded = await asyncio.wait_for(owner.process.stdout.readline(), timeout=40)
        assert 0 < len(encoded) <= 4096
        parent = _WindowsBrowserParent.model_validate_json(encoded)
        assert parent.runtime_pid > 0
        assert parent.runtime_pid == owner.process.pid or psutil.Process(parent.runtime_pid).ppid() == owner.process.pid
        rights = win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
        owner.handles[parent.runtime_pid] = win32api.OpenProcess(
            rights | win32con.PROCESS_TERMINATE, False, parent.runtime_pid
        )
        owner.runtime_pid = parent.runtime_pid
        parent_handle = owner.handles[parent.runtime_pid]
        assert win32event.WaitForSingleObject(parent_handle, 0) == win32event.WAIT_TIMEOUT
        assert win32process.GetProcessTimes(parent_handle)["CreationTime"].isoformat() == parent.created
        ready = await asyncio.wait_for(owner.process.stdout.readline(), timeout=100)
        assert ready in (b"ready\n", b"ready\r\n"), "real profile lease was not acknowledged"
        admission = await _windows_fixture_record(
            tmp_path / "windows-worker-admitted.json", _WindowsBrowserAdmission, owner
        )
        # Keep the selected installed interpreter even when its Windows venv
        # launcher retains an intermediate parent. Base Python would discard
        # the isolated private worker's installed environment.
        assert admission.runtime_pid == parent.runtime_pid
        assert admission.worker_pid > 0 and admission.worker_pid != admission.runtime_pid
        assert admission.buffer_wiped is True
        for pid in (admission.runtime_pid, admission.worker_pid):
            if pid not in owner.handles:
                owner.handles[pid] = win32api.OpenProcess(rights, False, pid)
            assert win32event.WaitForSingleObject(owner.handles[pid], 0) == win32event.WAIT_TIMEOUT
        # The owner acknowledges custody first; this explicit test barrier then
        # allows its already-contained worker to create real browser descendants.
        (tmp_path / "windows-start-browser").write_text("start", encoding="ascii")
        browser = await _windows_fixture_record(tmp_path / "windows-worker-browser.json", _WindowsBrowserReady, owner)
        assert browser.worker_pid == admission.worker_pid and browser.title == "synthetic containment"
        selected_executable = browser.executable.resolve(strict=True)
        assert selected_executable.is_file()
        members = await _windows_job_members(owner)
        assert admission.worker_pid in members and admission.runtime_pid not in members
        browser_roles: set[str] = set()
        for pid, created in members.items():
            if pid not in owner.handles:
                owner.handles[pid] = win32api.OpenProcess(rights, False, pid)
            handle = owner.handles[pid]
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
            assert win32process.GetProcessTimes(handle)["CreationTime"].isoformat() == created
            executable = Path(win32process.GetModuleFileNameEx(handle, 0)).resolve(strict=True)
            if executable == selected_executable:
                arguments = psutil.Process(pid).cmdline()
                if "--type=renderer" in arguments:
                    browser_roles.add("renderer")
                elif "--remote-debugging-pipe" in arguments and not any(
                    argument.startswith("--type=") for argument in arguments
                ):
                    browser_roles.add("browser")
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        assert browser_roles == {"browser", "renderer"}
        # A second exact-Job observation ties the held, live objects and their
        # native creation times to the owner rather than trusting reused PIDs.
        assert await _windows_job_members(owner) == members
        for handle in owner.handles.values():
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        win32api.TerminateProcess(owner.handles[admission.runtime_pid], 23)
        await asyncio.wait_for(owner.process.wait(), timeout=5)
        # These are the same held native objects, observed dead before the
        # cleanup owner can issue a graceful worker close or release a handle.
        for handle in owner.handles.values():
            assert win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
    finally:
        await close_async_resources(
            owner, task_name="windows-admitted-browser-fixture-close", primary_error=sys.exception()
        )
    assert owner.stderr == b""


class _WindowsHostRetirement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    runtime_pid: int
    worker_pid: int
    owner_lost: bool
    profile_removed: bool
    server_running: bool
    stop_requested: bool


@pytest.mark.asyncio
async def test_idle_admitted_worker_death_retires_browser_without_frontend_request(tmp_path: Path) -> None:
    """The real host poll retires an idle lost worker; native objects die before cleanup."""
    import psutil
    import win32api
    import win32con
    import win32event
    import win32process

    owner = _WindowsBrowserFixture(
        await asyncio.create_subprocess_exec(
            sys.executable,
            *fixture_arguments(
                "cadrumo.entrypoints.runtime.tests.windows_worker_parent_fixture",
                "host-browser-owner",
                str(tmp_path),
            ),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=fixture_environment(),
        )
    )
    primary: BaseException | None = None
    try:
        assert owner.process.stdout is not None
        encoded = await asyncio.wait_for(owner.process.stdout.readline(), timeout=40)
        assert 0 < len(encoded) <= 4096
        parent = _WindowsBrowserParent.model_validate_json(encoded)
        assert parent.runtime_pid > 0
        assert parent.runtime_pid == owner.process.pid or psutil.Process(parent.runtime_pid).ppid() == owner.process.pid
        rights = win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
        owner.handles[parent.runtime_pid] = win32api.OpenProcess(
            rights | win32con.PROCESS_TERMINATE, False, parent.runtime_pid
        )
        owner.runtime_pid = parent.runtime_pid
        parent_handle = owner.handles[parent.runtime_pid]
        assert win32event.WaitForSingleObject(parent_handle, 0) == win32event.WAIT_TIMEOUT
        assert win32process.GetProcessTimes(parent_handle)["CreationTime"].isoformat() == parent.created
        ready = await asyncio.wait_for(owner.process.stdout.readline(), timeout=100)
        assert ready in (b"ready\n", b"ready\r\n"), "real profile lease was not acknowledged"
        admission = await _windows_fixture_record(
            tmp_path / "windows-worker-admitted.json", _WindowsBrowserAdmission, owner
        )
        # Keep the selected installed interpreter even when its Windows venv
        # launcher retains an intermediate parent. Base Python would discard
        # the isolated private worker's installed environment.
        assert admission.runtime_pid == parent.runtime_pid
        assert admission.worker_pid > 0 and admission.worker_pid != admission.runtime_pid
        assert admission.buffer_wiped is True
        for pid in (admission.runtime_pid, admission.worker_pid):
            if pid not in owner.handles:
                owner.handles[pid] = win32api.OpenProcess(
                    rights | (win32con.PROCESS_TERMINATE if pid == admission.worker_pid else 0), False, pid
                )
            assert win32event.WaitForSingleObject(owner.handles[pid], 0) == win32event.WAIT_TIMEOUT
        # The owner acknowledges custody first; this explicit test barrier then
        # allows its already-contained worker to create real browser descendants.
        (tmp_path / "windows-start-browser").write_text("start", encoding="ascii")
        browser = await _windows_fixture_record(tmp_path / "windows-worker-browser.json", _WindowsBrowserReady, owner)
        assert browser.worker_pid == admission.worker_pid and browser.title == "synthetic containment"
        selected_executable = browser.executable.resolve(strict=True)
        assert selected_executable.is_file()
        members = await _windows_job_members(owner)
        assert admission.worker_pid in members and admission.runtime_pid not in members
        browser_roles: set[str] = set()
        for pid, created in members.items():
            if pid not in owner.handles:
                owner.handles[pid] = win32api.OpenProcess(rights, False, pid)
            handle = owner.handles[pid]
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
            assert win32process.GetProcessTimes(handle)["CreationTime"].isoformat() == created
            executable = Path(win32process.GetModuleFileNameEx(handle, 0)).resolve(strict=True)
            if executable == selected_executable:
                arguments = psutil.Process(pid).cmdline()
                if "--type=renderer" in arguments:
                    browser_roles.add("renderer")
                elif "--remote-debugging-pipe" in arguments and not any(
                    argument.startswith("--type=") for argument in arguments
                ):
                    browser_roles.add("browser")
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        assert browser_roles == {"browser", "renderer"}
        # A second exact-Job observation ties the held, live objects and their
        # native creation times to the owner rather than trusting reused PIDs.
        assert await _windows_job_members(owner) == members
        for handle in owner.handles.values():
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        win32api.TerminateProcess(owner.handles[admission.worker_pid], 23)
        # No command or frontend request follows the kill. The original host's
        # independent poll must contain the scope while its native parent lives.
        deadline = time.monotonic() + 15
        descendant_handles = [handle for pid, handle in owner.handles.items() if pid != admission.runtime_pid]
        while any(
            win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_OBJECT_0 for handle in descendant_handles
        ):
            assert time.monotonic() < deadline, "idle worker death did not retire its observed descendants"
            assert win32event.WaitForSingleObject(parent_handle, 0) == win32event.WAIT_TIMEOUT
            await asyncio.sleep(0.02)
        retired = await _windows_fixture_record(tmp_path / "windows-host-retired.json", _WindowsHostRetirement, owner)
        assert retired.runtime_pid == admission.runtime_pid and retired.worker_pid == admission.worker_pid
        assert retired.owner_lost and retired.profile_removed and retired.server_running and not retired.stop_requested
        assert win32event.WaitForSingleObject(parent_handle, 0) == win32event.WAIT_TIMEOUT
        assert owner.process.returncode is None
        assert all(
            win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_OBJECT_0 for handle in descendant_handles
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        await close_async_resources(owner, task_name="windows-admitted-browser-fixture-close", primary_error=primary)
    assert owner.stderr == b""
