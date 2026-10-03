"""Demand-driven recovery of an installed Windows runtime after an exact crash.

Only initial profile/grant preparation uses typed synthetic human provenance.
Enrollment writes directly to real Credential Manager. Both installed runtime
boots, desktop login observation, SDK admissions and private workers are real.
This does not establish unattended scheduler restart or uncertain-write replay.
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import sys
import sysconfig
import time
from collections.abc import Callable
from contextlib import AsyncExitStack, ExitStack
from ctypes import wintypes
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.service_definitions import runtime_service_name
from cadrumo.adapters.local_runtime.tests import test_windows_manager_stop_native as task_fixture
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_manager import WindowsTaskManager, windows_task_binding_matches
from cadrumo.adapters.local_runtime.windows_task_process import task_engine_owns_process
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_store import (
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
    retire_profile_automation,
)
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject, changed
from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeManagerProcessState, RuntimeServiceBinding
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.profile_access import (
    PROFILE_ADMISSION_TIMEOUT_SECONDS,
    RuntimeAccessRefusal,
    RuntimeSessionRequest,
)
from cadrumo.application.runtime.transport import RuntimeStatusRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, NativeSecretBackend
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path

from .test_installed_authenticated_stdio import _installed_mcp_executable, _scope_for_auth_read
from .test_installed_mcp_tui_grant_parity import _private_read, _record, _status

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the installed Windows runtime and normal desktop"),
]

type _Stage = Literal[
    "setup_complete",
    "task_configured",
    "first_initialized",
    "first_read",
    "first_owned",
    "first_crashed",
    "old_fenced",
    "replacement_initialized",
    "replacement_read",
    "replacement_owned",
    "stale_refused",
    "drain_enter",
    "drain_accepted",
    "cleanup_enter",
    "cleanup_exited",
]


class _NativeTask(Protocol):
    Xml: str
    Path: str


class _NativeTaskFolder(Protocol):
    GetTask: Callable[[str], _NativeTask]


class _NativeRunningTask(Protocol):
    Path: str
    InstanceGuid: str
    EnginePID: int
    Refresh: Callable[[], None]


class _NativeRunningTasks(Protocol):
    Count: int
    Item: Callable[[int], _NativeRunningTask]


class _NativeScheduler(Protocol):
    Connect: Callable[[], None]
    GetFolder: Callable[[str], _NativeTaskFolder]
    GetRunningTasks: Callable[[int], _NativeRunningTasks]


class _RetainedProcess:
    """Retain one live process incarnation before any crash or cleanup action."""

    def __init__(self, pid: int) -> None:
        """Open an ancestry-selected live PID and verify its unchanged birth."""
        self.pid = pid
        self.kernel = task_fixture._win_library("kernel32")
        self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        before = task_fixture._process_creation_identity(pid)
        assert before is not None, "owned process was not live before handle capture"
        handle = cast(int, self.kernel.OpenProcess(0x1000 | 0x100000 | 0x1, False, pid))
        assert handle, "owned process could not be retained"
        self.handle: int | None = handle
        try:
            self.kernel.GetProcessTimes.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            )
            self.kernel.GetProcessTimes.restype = wintypes.BOOL
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            assert self.kernel.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
            )
            self.birth = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
            assert self.birth == before == task_fixture._process_creation_identity(pid)
            assert self.alive()
        except BaseException:
            self.close()
            raise

    def alive(self) -> bool:
        """Check the retained handle, without reopening a possibly reused PID."""
        handle = self.handle
        assert handle is not None
        result: object = self.kernel.WaitForSingleObject(handle, 0)
        assert isinstance(result, int), "native process wait did not return an integer"
        assert result in {0, 0x102}, "retained process wait failed"
        return result == 0x102

    def terminate(self) -> None:
        """Crash only the already retained process incarnation."""
        handle = self.handle
        assert handle is not None
        if self.alive():
            terminated: object = self.kernel.TerminateProcess(handle, 0x80004005)
            assert isinstance(terminated, int), "native termination did not return an integer"
            if terminated == 0:
                error_code = ctypes.get_last_error()
                # Another exact-owner shutdown may win between the preceding
                # wait and TerminateProcess. Require actual retained-handle
                # termination; a cached PID or optimistic liveness is invalid.
                settled: object = self.kernel.WaitForSingleObject(handle, 1000)
                assert isinstance(settled, int), "native termination settlement did not return an integer"
                assert settled == 0, f"exact retained process remains unsettled; native error {error_code}"

    def close(self) -> None:
        """Retire the handle only after native close succeeds."""
        handle = self.handle
        if handle is not None:
            assert self.kernel.CloseHandle(handle)
            self.handle = None


def _retain_owned_tree(
    engine_pid: int, runtime_pid: int, handles: ExitStack, *, require_worker: bool = True
) -> tuple[_RetainedProcess, ...]:
    """Retain only native ancestry members of the verified task/runtime."""
    kernel = task_fixture._win_library("kernel32")
    enumerate_processes = kernel.K32EnumProcesses
    enumerate_processes.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    enumerate_processes.restype = wintypes.BOOL
    buffer = (wintypes.DWORD * 4096)()
    used = wintypes.DWORD()
    assert enumerate_processes(buffer, ctypes.sizeof(buffer), ctypes.byref(used))
    assert used.value < ctypes.sizeof(buffer), "native process snapshot exceeded its fixed bound"
    owned: list[_RetainedProcess] = []
    for pid in buffer[: used.value // ctypes.sizeof(wintypes.DWORD)]:
        if pid > 0 and (task_engine_owns_process(engine_pid, pid) or task_engine_owns_process(runtime_pid, pid)):
            process = _RetainedProcess(pid)
            handles.callback(process.close)
            assert task_engine_owns_process(engine_pid, pid) or task_engine_owns_process(runtime_pid, pid)
            owned.append(process)
    assert any(process.pid == runtime_pid for process in owned)
    if require_worker:
        assert any(
            process.pid != runtime_pid and task_engine_owns_process(runtime_pid, process.pid) for process in owned
        ), "private admission did not expose a live owned worker descendant"
    return tuple(owned)


def _instance(
    binding: RuntimeServiceBinding, task_name: str, identity: task_fixture._XmlShape, runtime_pid: int | None
) -> tuple[UUID, int]:
    """Inspect public native hidden-task identity between canonical XML bookends."""
    import pythoncom
    import win32com.client

    def inspect() -> tuple[UUID, int] | None:
        service = cast(_NativeScheduler, win32com.client.Dispatch("Schedule.Service"))
        service.Connect()
        folder = service.GetFolder("\\")
        task = folder.GetTask(task_name)
        expected_path = "\\" + task_name
        if (
            task.Path != expected_path
            or not windows_task_binding_matches(task.Xml, binding, login_autostart=False)
            or task_fixture._normalize_registered_xml(task.Xml) != identity
        ):
            return None
        instances = service.GetRunningTasks(1)
        if not 0 <= instances.Count <= 4096:
            return None
        selected: tuple[UUID, int] | None = None
        for index in range(1, instances.Count + 1):
            candidate = instances.Item(index)
            if candidate.Path != expected_path:
                continue
            candidate.Refresh()
            if candidate.Path != expected_path or selected is not None:
                return None
            raw_guid = candidate.InstanceGuid
            try:
                guid = UUID(raw_guid)
            except ValueError:
                return None
            if not guid.int or raw_guid.lower() not in {str(guid), "{" + str(guid) + "}"}:
                return None
            engine_pid = candidate.EnginePID
            if engine_pid <= 0 or not task_engine_owns_process(
                engine_pid, runtime_pid if runtime_pid is not None else engine_pid
            ):
                return None
            selected = guid, engine_pid
        verified = folder.GetTask(task_name)
        if (
            verified.Path != expected_path
            or not windows_task_binding_matches(verified.Xml, binding, login_autostart=False)
            or task_fixture._normalize_registered_xml(verified.Xml) != identity
        ):
            return None
        return selected

    initialize = cast(Callable[[int], None], pythoncom.CoInitializeEx)
    initialize(pythoncom.COINIT_APARTMENTTHREADED)
    selected: tuple[UUID, int] | None = None
    unavailable = False
    try:
        try:
            selected = inspect()
        except pythoncom.com_error:
            unavailable = True
    finally:
        # Native wrappers and handled COM-error frames have left inspect's
        # scope before the calling thread releases its COM apartment.
        pythoncom.CoUninitialize()
    assert not unavailable, "native scheduler identity inspection unavailable"
    assert selected is not None, "native exact task/process identity was not proven"
    return selected


def _probe(endpoint: WindowsRuntimeEndpoint, product_version: str) -> tuple[VerifiedRuntimeConnection, int]:
    """Pin a new public handshake to the native server process identity."""
    channel = endpoint.connect(timeout=5)
    connection = VerifiedRuntimeConnection(
        channel,
        expected=RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 5,
    )
    pid = channel.peer.process_id
    if pid is None:
        connection.close()
        raise AssertionError("native runtime handshake lacked its actual process identity")
    return connection, pid


async def _wait_gone(processes: tuple[_RetainedProcess, ...], *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while any(process.alive() for process in processes):
        assert time.monotonic() < deadline, "exact retained runtime/worker processes remained live"
        await asyncio.sleep(0.05)


async def _drain(connection: VerifiedRuntimeConnection) -> None:
    preview = await asyncio.to_thread(
        connection.owner_control, RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 5
    )
    assert isinstance(preview, RuntimeStopPreview)
    accepted = await asyncio.to_thread(
        connection.owner_control,
        RuntimeStopConfirm(
            request_id=uuid4(),
            runtime_boot_id=preview.runtime_boot_id,
            preview_id=preview.preview_id,
            acknowledge_all_profiles_and_work=True,
        ),
        deadline=time.monotonic() + 8,
    )
    assert isinstance(accepted, RuntimeStopAccepted)


@pytest.mark.asyncio
async def test_installed_windows_sdk_reconnects_after_exact_runtime_crash(tmp_path: Path) -> None:
    """Fresh SDK demand replaces a dead host without retargeting or replay."""
    require_selected_normal_desktop()
    runtime_executable = Path(sysconfig.get_path("scripts")) / "cadrumo-runtime.exe"
    mcp_executable = _installed_mcp_executable()
    assert runtime_executable.is_file() and mcp_executable.is_file(), "requires the inspected installed build"
    root = (tmp_path / "cadrumo-storage").resolve()
    root.mkdir()
    task_fixture._require_temp_child(root)
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    product_version = version("cadrumo")
    binding = RuntimeServiceBinding(
        executable=str(runtime_executable.resolve(strict=True)),
        storage_root=str(root),
        storage_identity=endpoint.storage_identity,
        os_owner_id=endpoint.os_owner_id,
        product_version=product_version,
    )
    installation = runtime_installation(
        storage_root=root, os_owner_id=binding.os_owner_id, storage_identity=endpoint.storage_identity
    )
    manager, task_name = WindowsTaskManager(binding), runtime_service_name(binding)
    native = native_automation_secret_store(NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER)
    assert native.backend is NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER
    with (
        administration_subject(
            tmp_path,
            os_owner_id=binding.os_owner_id,
            installation_id=installation.installation_id,
            profile_label="Installed runtime crash recovery",
        ) as subject,
        ExitStack() as handles,
    ):
        handles.callback(endpoint.close)
        # This trusted setup creates a synthetic initial grant. It starts no
        # server and injects no login observation into either installed host.
        assert native.read(CONTROL_NAMESPACE, subject.store.account) is None
        subject.store.secrets = native
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(requester=requester, secrets_store=native)
        scope = _scope_for_auth_read(requester.client_id)
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        subject.proposal = changed(subject.proposal, scope=scope)
        request_id = uuid4()
        protected = NativeClientCredentialStore(
            secrets_store=native,
            binding=subject.store.binding,
            client_id=requester.client_id,
            destination_id=requester.destination_id,
        )
        try:
            subject.service.request(request_id, subject.proposal)
            receipt = subject.approve(request_id)
            assert receipt.credential_reference is not None and receipt.key_id is not None
            metadata = protected.inspect(credential_reference=receipt.credential_reference)
            assert (metadata.grant_id, metadata.key_id) == (receipt.grant_id, receipt.key_id)
        except BaseException:
            # No runtime exists yet. A failed approval can nevertheless have
            # published a candidate into this exact recipient's native store.
            requests = subject.store.enrollment_state().requests
            for record in requests:
                if (
                    record.request_id == request_id
                    and record.credential_reference is not None
                    and record.candidate_key_id is not None
                ):
                    protected.delete(
                        credential_reference=record.credential_reference,
                        grant_id=record.grant_id,
                        key_id=record.candidate_key_id,
                        review_digest=enrollment_review_digest(record),
                    )
            assert retire_profile_automation(
                root=root, profile_id=subject.store.binding.profile_id, secrets_store=native
            )
            raise
        initial_payload = subject.store.read()[1]
        grant = next(entry.grant for entry in initial_payload.grants if entry.grant.grant_id == metadata.grant_id)
        wrap_accounts = tuple(
            subject.store.account + "/" + str(entry.wrap_key_id)
            for entry in initial_payload.grants
            if entry.wrap_key_id is not None
        )
        close_active_bucket_session()
        parameters = StdioServerParameters(
            command=str(mcp_executable),
            args=[
                "--profile-id",
                str(metadata.profile_id),
                "--credential-reference",
                str(metadata.credential_reference),
            ],
            cwd=tmp_path,
            env={
                "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                "PYDANTIC_DISABLE_PLUGINS": "__all__",
            },
        )
        identity: task_fixture._XmlShape | None = None
        probes: list[VerifiedRuntimeConnection] = []
        processes: list[_RetainedProcess] = []
        sdk_resources = AsyncExitStack()
        uncaptured_admission = False
        primary: BaseException | None = None
        started_at = time.monotonic()
        artifact = tmp_path / "installed-runtime-recovery-ownership.json"
        cleanup_outcomes = {
            "sdk_closed": False,
            "probes_closed": False,
            "runtime_quiescent": False,
            "task_deleted": False,
            "server_custody_retired": False,
            "client_item_deleted": False,
            "native_server_records_absent": False,
        }
        evidence: dict[str, object] = {
            "storage_root": str(root),
            "profile_id": str(metadata.profile_id),
            "installation_id": str(installation.installation_id),
            "cleanup": cleanup_outcomes,
        }

        def checkpoint(stage: _Stage) -> None:
            evidence["phase"] = stage
            evidence["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
            artifact.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

        checkpoint("setup_complete")
        try:
            before = await manager.inspect()
            assert before.available and not before.provisioned
            configured = await manager.configure(login_autostart=False)
            assert configured.binding_matches and not configured.login_autostart
            identity = task_fixture._owned_installed_task_identity(task_name, binding)
            assert identity is not None
            evidence["task_xml_identity_sha256"] = sha256(canonical_json_bytes(identity)).hexdigest()
            assert (await manager.inspect()).process_state is RuntimeManagerProcessState.STOPPED
            checkpoint("task_configured")
            with (tmp_path / "first-sdk-stderr.txt").open("w", encoding="utf-8") as errlog:
                uncaptured_admission = True
                read, write = await sdk_resources.enter_async_context(stdio_client(parameters, errlog=errlog))
                first = await sdk_resources.enter_async_context(
                    ClientSession(read, write, read_timeout_seconds=PROFILE_ADMISSION_TIMEOUT_SECONDS + 5)
                )
                await first.initialize()
                checkpoint("first_initialized")
                first_status = _status(
                    _record((await first.call_tool("status", {})).structured_content), metadata.profile_id
                )
                assert first_status.effective_scope == scope
                first_result = await _private_read(first, metadata.profile_id)
                checkpoint("first_read")
                old_probe, first_pid = await asyncio.to_thread(_probe, endpoint, product_version)
                probes.append(old_probe)
                first_boot = old_probe.hello.boot_id
                first_guid, first_engine = await asyncio.to_thread(_instance, binding, task_name, identity, first_pid)
                first_tree = await asyncio.to_thread(_retain_owned_tree, first_engine, first_pid, handles)
                processes.extend(first_tree)
                uncaptured_admission = False
                evidence["first_host"] = {
                    "runtime_pid": first_pid,
                    "boot_id": str(first_boot),
                    "task_guid": str(first_guid),
                    "engine_pid": first_engine,
                    "retained_tree": [{"pid": process.pid, "birth": process.birth} for process in first_tree],
                }
                checkpoint("first_owned")
                actual_runtime = next(process for process in first_tree if process.pid == first_pid)
                # Terminate the pipe's retained, ancestry-verified actual host,
                # rather than its console-script or pythonw redirector parent.
                actual_runtime.terminate()
                await _wait_gone(first_tree, timeout=17)
                checkpoint("first_crashed")
                with pytest.raises(RuntimeRefusalError) as closed:
                    await asyncio.to_thread(
                        old_probe.status, RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 5
                    )
                assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
                retired = await first.call_tool("result", {"result": first_result.model_dump(mode="json")})
                refused = _record(retired.structured_content)
                assert retired.is_error and refused["outcome"] == "refused", refused
                assert refused["code"] in {
                    RuntimeRefusalCode.CONNECTION_CLOSED.value,
                    AccessDenialCode.SESSION_INACTIVE.value,
                    AccessDenialCode.CONNECTION_MISMATCH.value,
                }
                old_probe.close()
                probes.remove(old_probe)
                # Release every old named-pipe handle before replacement; the
                # previous SDK connection remains fenced until it is closed.
                await sdk_resources.aclose()
                checkpoint("old_fenced")
            assert not (await manager.inspect()).login_autostart
            with (tmp_path / "replacement-sdk-stderr.txt").open("w", encoding="utf-8") as errlog:
                uncaptured_admission = True
                read, write = await sdk_resources.enter_async_context(stdio_client(parameters, errlog=errlog))
                replacement = await sdk_resources.enter_async_context(
                    ClientSession(read, write, read_timeout_seconds=PROFILE_ADMISSION_TIMEOUT_SECONDS + 5)
                )
                await replacement.initialize()
                checkpoint("replacement_initialized")
                replacement_status = _status(
                    _record((await replacement.call_tool("status", {})).structured_content),
                    metadata.profile_id,
                )
                assert replacement_status.session_id != first_status.session_id
                assert replacement_status.effective_scope == scope
                second_result = await _private_read(replacement, metadata.profile_id)
                checkpoint("replacement_read")
                assert second_result.operation_id != first_result.operation_id
                assert second_result.definition_contract_digest == first_result.definition_contract_digest
                assert second_result.result_schema == first_result.result_schema
                new_probe, second_pid = await asyncio.to_thread(_probe, endpoint, product_version)
                probes.append(new_probe)
                second_boot = new_probe.hello.boot_id
                assert second_boot != first_boot
                second_guid, second_engine = await asyncio.to_thread(
                    _instance, binding, task_name, identity, second_pid
                )
                assert second_guid != first_guid
                second_tree = await asyncio.to_thread(_retain_owned_tree, second_engine, second_pid, handles)
                processes.extend(second_tree)
                uncaptured_admission = False
                evidence["replacement_host"] = {
                    "runtime_pid": second_pid,
                    "boot_id": str(second_boot),
                    "task_guid": str(second_guid),
                    "engine_pid": second_engine,
                    "retained_tree": [{"pid": process.pid, "birth": process.birth} for process in second_tree],
                }
                checkpoint("replacement_owned")
                assert first_status.session_id is not None
                stale = await asyncio.to_thread(
                    new_probe.session,
                    RuntimeSessionRequest(
                        action="session_status",
                        request_id=uuid4(),
                        profile_id=metadata.profile_id,
                        session_id=first_status.session_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(stale, RuntimeAccessRefusal)
                # This fresh public connection has never authenticated. The
                # previous lease UUID cannot create a connection or authority.
                assert stale.code is AutomationCustodyCode.CREDENTIAL_REJECTED
                checkpoint("stale_refused")
                assert protected.inspect(credential_reference=metadata.credential_reference) == metadata
                current = subject.store.read()[1]
                assert (
                    next(entry.grant for entry in current.grants if entry.grant.grant_id == metadata.grant_id) == grant
                )
                inspection = await manager.inspect()
                assert inspection.binding_matches and not inspection.login_autostart
                await sdk_resources.aclose()
                # A refused session request still marks a connection as used
                # for private work. Owner control requires a dedicated channel.
                new_probe.close()
                probes.remove(new_probe)
                owner_probe, owner_pid = await asyncio.to_thread(_probe, endpoint, product_version)
                probes.append(owner_probe)
                assert owner_probe.hello.boot_id == second_boot
                assert owner_pid == second_pid
                checkpoint("drain_enter")
                await _drain(owner_probe)
                checkpoint("drain_accepted")
                owner_probe.close()
                probes.remove(owner_probe)
                await _wait_gone(second_tree, timeout=25)
        except BaseException as error:
            primary = error
            raise
        finally:

            async def settle(original: BaseException | None) -> None:
                errors: list[BaseException] = []

                def attempt(action: Callable[[], None]) -> bool:
                    try:
                        action()
                    except BaseException as failure:
                        errors.append(failure)
                        return False
                    return True

                checkpoint("cleanup_enter")
                try:
                    await sdk_resources.aclose()
                except BaseException as failure:
                    errors.append(failure)
                else:
                    cleanup_outcomes["sdk_closed"] = True
                cleanup_outcomes["probes_closed"] = all([attempt(probe.close) for probe in probes])
                quiescent = False
                try:
                    # A partial configure may still have created our exact
                    # definition. Substitution refuses all task mutations.
                    owned_identity = task_fixture._owned_installed_task_identity(task_name, binding)
                    if owned_identity is not None:
                        assert identity is None or identity == owned_identity
                        if task_fixture._task_state(task_name, owned_identity) == task_fixture._TASK_RUNNING:
                            _, cleanup_engine = await asyncio.to_thread(
                                _instance, binding, task_name, owned_identity, None
                            )
                            cleanup_tree = await asyncio.to_thread(
                                _retain_owned_tree, cleanup_engine, cleanup_engine, handles, require_worker=False
                            )
                            processes.extend(cleanup_tree)
                        attempt(lambda: task_fixture._stop_task(task_name, owned_identity))
                        for process in processes:
                            attempt(process.terminate)
                        await _wait_gone(tuple(processes), timeout=25)
                        deadline = time.monotonic() + 25
                        while task_fixture._task_state(task_name, owned_identity) == task_fixture._TASK_RUNNING:
                            assert time.monotonic() < deadline, "owned task remained running during cleanup"
                            await asyncio.sleep(0.05)
                        quiescent = True
                        cleanup_outcomes["task_deleted"] = attempt(
                            lambda: task_fixture._delete_task(task_name, owned_identity)
                        )
                    else:
                        assert not uncaptured_admission, "runtime admission has no retained cleanup identity"
                        assert not any(process.alive() for process in processes)
                        quiescent = True
                        cleanup_outcomes["task_deleted"] = True
                except BaseException as failure:
                    errors.append(failure)
                cleanup_outcomes["runtime_quiescent"] = quiescent
                if quiescent:

                    def retire() -> None:
                        assert retire_profile_automation(
                            root=root, profile_id=metadata.profile_id, secrets_store=native
                        )

                    cleanup_outcomes["server_custody_retired"] = attempt(retire)
                    cleanup_outcomes["client_item_deleted"] = attempt(
                        lambda: protected.delete(
                            credential_reference=metadata.credential_reference,
                            grant_id=metadata.grant_id,
                            key_id=metadata.key_id,
                            review_digest=metadata.review_digest,
                        )
                    )

                    def absent() -> None:
                        assert native.read(CONTROL_NAMESPACE, subject.store.account) is None
                        assert all(native.read(WRAP_NAMESPACE, account) is None for account in wrap_accounts)

                    cleanup_outcomes["native_server_records_absent"] = attempt(absent)
                attempt(endpoint.close)
                evidence["cleanup_failure_count"] = len(errors)
                checkpoint("cleanup_exited")
                if errors:
                    if original is None:
                        raise BaseExceptionGroup("exact installed recovery cleanup failed", errors)
                    original.add_note(f"exact recovery cleanup failures: {len(errors)}; ownership artifact: {artifact}")
                    original.__dict__["installed_recovery_cleanup_errors"] = tuple(errors)

            await await_cancellation_complete(settle(primary), task_name="installed-runtime-recovery-cleanup")
