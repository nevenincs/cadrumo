"""Controlled scheduler ports prove exact-instance stop ordering and refusals.

These portable tests do not establish native COM stop or scheduler restart
behavior. The actual scheduler boundary is replaced with typed local ports.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Literal, cast
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

from .. import windows_managed_stop, windows_manager
from ..service_definitions import runtime_service_name, windows_task_xml
from ..windows_managed_stop import WindowsManagedRuntimeStop
from ..windows_manager import WindowsTaskManager, _RegisteredTask, _RunningTask, _TaskFolder, _TaskService
from . import windows_managed_runtime_fixture as stop_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@dataclass
class _InstanceProbe:
    Path: str = ""
    InstanceGuid: str = field(default_factory=lambda: "{" + str(uuid4()).upper() + "}")
    EnginePID: int = 4242
    refreshes: int = 0
    stops: int = 0
    stop_refusal: RuntimeRefusalCode | None = None
    refreshed_path: str | None = None

    def refresh(self) -> None:
        self.refreshes += 1
        if self.refreshed_path is not None:
            self.Path = self.refreshed_path

    def stop(self) -> None:
        self.stops += 1
        if self.stop_refusal is not None:
            raise RuntimeRefusalError(self.stop_refusal)

    Refresh = refresh
    Stop = stop


@dataclass
class _InstancesProbe:
    instance: _InstanceProbe = field(default_factory=_InstanceProbe)
    Count: int = 1
    members: tuple[_InstanceProbe, ...] | None = None

    def item(self, index: int) -> _RunningTask:
        assert 1 <= index <= self.Count
        value = self.instance if self.members is None else self.members[index - 1]
        return cast(_RunningTask, value)

    Item = item


@dataclass
class _TaskProbe:
    Xml: str
    Path: str
    instances: _InstancesProbe = field(default_factory=_InstancesProbe)
    Enabled: bool = True


@dataclass
class _StopFixture:
    managed: WindowsManagedRuntimeStop
    manager: WindowsTaskManager
    task: _TaskProbe
    stop: Event
    health_checks: list[tuple[int, int]]
    owns_process: bool = True


@pytest.fixture
def stop_fixture(monkeypatch: pytest.MonkeyPatch) -> _StopFixture:
    binding = RuntimeServiceBinding(
        executable=r"C:\Synthetic runtime\pythonw.exe",
        storage_root=r"C:\Synthetic runtime\profiles",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001",
        product_version="test-cohort",
    )
    # Native endpoint construction is separately covered. These initialized
    # manager fields bind the pure canonical XML/ownership decision methods.
    manager = object.__new__(WindowsTaskManager)
    manager._binding = binding
    manager._name = runtime_service_name(binding)
    task = _TaskProbe(windows_task_xml(binding, login_autostart=True), "\\" + manager._name)
    task.instances.instance.Path = task.Path
    health_checks: list[tuple[int, int]] = []
    stop = Event()

    def construct_manager(actual_binding: RuntimeServiceBinding) -> WindowsTaskManager:
        assert actual_binding == binding
        return manager

    monkeypatch.setattr(windows_managed_stop, "WindowsTaskManager", construct_manager)
    fixture = _StopFixture(WindowsManagedRuntimeStop(binding, stop), manager, task, stop, health_checks)

    def find_task(_manager: WindowsTaskManager, _folder: _TaskFolder) -> _RegisteredTask:
        assert _manager is manager
        return cast(_RegisteredTask, task)

    class _ServiceProbe:
        def get_folder(self, path: str) -> _TaskFolder:
            assert path == "\\"
            return cast(_TaskFolder, object())

        def get_running_tasks(self, flags: int) -> _InstancesProbe:
            assert flags == 1
            return task.instances

        GetFolder = get_folder
        GetRunningTasks = get_running_tasks

    def scheduler_call[Result](operation: Callable[[_TaskService], Result]) -> Result:
        return operation(cast(_TaskService, _ServiceProbe()))

    def owns_process(engine_pid: int, process_pid: int) -> bool:
        health_checks.append((engine_pid, process_pid))
        return fixture.owns_process

    monkeypatch.setattr(WindowsTaskManager, "_find", find_task)
    monkeypatch.setattr(windows_manager, "_scheduler_service_call", scheduler_call)
    monkeypatch.setattr(windows_manager, "task_engine_owns_process", owns_process)
    return fixture


def test_prepare_never_stops_and_finalize_rechecks_after_shutdown_signal(stop_fixture: _StopFixture) -> None:
    fixture = stop_fixture
    with fixture.managed:
        fixture.managed()
        assert fixture.task.instances.instance.stops == 0
        assert not fixture.stop.is_set()
        assert fixture.health_checks == [(4242, os.getpid())]
        with pytest.raises(RuntimeRefusalError) as early:
            fixture.managed.finalize()
        assert early.value.reason is RuntimeRefusalCode.UNAVAILABLE
        assert fixture.task.instances.instance.stops == 0
        fixture.stop.set()
        fixture.managed.finalize()
        assert fixture.task.instances.instance.stops == 1
        assert fixture.task.instances.instance.refreshes == 2
        assert fixture.health_checks == [(4242, os.getpid()), (4242, os.getpid())]
        with pytest.raises(RuntimeRefusalError):
            fixture.managed.finalize()
        with pytest.raises(RuntimeRefusalError):
            fixture.managed()
        assert fixture.task.instances.instance.stops == 1


@pytest.mark.parametrize("change", ["guid", "engine", "definition", "autostart", "ambiguous", "dead"])
def test_finalization_refuses_substitution_before_native_stop(
    stop_fixture: _StopFixture,
    change: Literal["guid", "engine", "definition", "autostart", "ambiguous", "dead"],
) -> None:
    fixture = stop_fixture
    fixture.managed()
    fixture.stop.set()
    if change == "guid":
        fixture.task.instances.instance.InstanceGuid = str(uuid4())
    elif change == "engine":
        fixture.task.instances.instance.EnginePID += 1
    elif change == "definition":
        fixture.task.Xml = fixture.task.Xml.replace("test-cohort", "other-cohort")
    elif change == "autostart":
        fixture.task.Xml = windows_task_xml(fixture.manager._binding, login_autostart=False)
    elif change == "ambiguous":
        fixture.task.instances.Count = 2
    else:
        fixture.owns_process = False
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.managed.finalize()
    assert refusal.value.reason is (
        RuntimeRefusalCode.VERSION_MISMATCH
        if change in {"definition", "autostart"}
        else RuntimeRefusalCode.PEER_UNTRUSTED
    )
    assert fixture.task.instances.instance.stops == 0


def test_native_stop_failure_retains_proof_and_retry_rechecks_it(stop_fixture: _StopFixture) -> None:
    fixture = stop_fixture
    fixture.managed()
    fixture.stop.set()
    fixture.task.instances.instance.stop_refusal = RuntimeRefusalCode.UNAVAILABLE
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.managed.finalize()
    assert refusal.value.reason is RuntimeRefusalCode.UNAVAILABLE
    fixture.task.instances.instance.stop_refusal = None
    fixture.managed.finalize()
    assert fixture.task.instances.instance.stops == 2
    assert fixture.task.instances.instance.refreshes == 3
    assert fixture.health_checks == [(4242, os.getpid())] * 3


def test_retained_proof_never_authorizes_a_different_current_process(stop_fixture: _StopFixture) -> None:
    fixture = stop_fixture
    identity = fixture.manager.prepare_current_process_stop()
    foreign = replace(identity, process_pid=identity.process_pid + 1)
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.manager.finalize_current_process_stop(foreign)
    assert refusal.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert fixture.task.instances.instance.stops == 0


@pytest.mark.parametrize("guid", ["not-a-guid", "00000000-0000-0000-0000-000000000000", uuid4().hex])
def test_preparation_refuses_missing_or_noncanonical_incarnation(stop_fixture: _StopFixture, guid: str) -> None:
    fixture = stop_fixture
    fixture.task.instances.instance.InstanceGuid = guid
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.managed()
    assert refusal.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert fixture.task.instances.instance.stops == 0
    assert not fixture.health_checks


def test_unrelated_hidden_tasks_are_excluded_before_identity_and_stop(stop_fixture: _StopFixture) -> None:
    fixture = stop_fixture
    foreign = _InstanceProbe(Path="\\foreign-task", InstanceGuid="unread", EnginePID=0)
    fixture.task.instances.members = (foreign, fixture.task.instances.instance)
    fixture.task.instances.Count = 2
    fixture.managed()
    fixture.stop.set()
    fixture.managed.finalize()
    assert fixture.task.instances.instance.stops == 1
    assert foreign.refreshes == foreign.stops == 0


@pytest.mark.parametrize("change", ["registered_path", "instance_path", "refreshed_path", "empty", "excessive"])
def test_hidden_enumeration_never_substitutes_task_path_or_inventory(stop_fixture: _StopFixture, change: str) -> None:
    fixture = stop_fixture
    if change == "registered_path":
        fixture.task.Path = "\\foreign-task"
    elif change == "instance_path":
        fixture.task.instances.instance.Path = "\\foreign-task"
    elif change == "refreshed_path":
        fixture.task.instances.instance.refreshed_path = "\\foreign-task"
    else:
        fixture.task.instances.Count = 0 if change == "empty" else 4097
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.managed()
    assert refusal.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert fixture.task.instances.instance.stops == 0
    assert not fixture.health_checks


def test_definition_changed_during_native_ancestry_check_never_authorizes_stop(
    stop_fixture: _StopFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = stop_fixture

    def changed_definition(_engine: int, _process: int) -> bool:
        fixture.task.Xml = fixture.task.Xml.replace("test-cohort", "other-cohort")
        return True

    monkeypatch.setattr(windows_manager, "task_engine_owns_process", changed_definition)
    with pytest.raises(RuntimeRefusalError) as refusal:
        fixture.managed()
    assert refusal.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    assert fixture.task.instances.instance.stops == 0


@dataclass
class _ProbePorts:
    entered: Event = field(default_factory=Event)
    release: Event = field(default_factory=Event)
    finished: Event = field(default_factory=Event)
    stops: int = 0
    cleanups: int = 0
    wait_error: BaseException | None = None
    release_error: BaseException | None = None
    stop_error: BaseException | None = None


@pytest.fixture
def probe_ports(monkeypatch: pytest.MonkeyPatch) -> _ProbePorts:
    """Replace scheduler calls, retaining real owned Thread/Event/Future settlement."""
    ports = _ProbePorts()

    def endpoint(*, storage_root: Path) -> stop_probe.WindowsRuntimeEndpoint:
        assert storage_root.is_absolute()
        return cast(stop_probe.WindowsRuntimeEndpoint, SimpleNamespace(storage_identity="a" * 64))

    def register(_name: str, xml: str, _owner: str) -> str:
        return xml

    def stop(_name: str, _identity: stop_probe.WindowsTaskXmlShape) -> None:
        ports.stops += 1
        ports.entered.set()
        try:
            if not ports.release.wait(5):
                raise TimeoutError("controlled scheduler Stop was not released")
            if ports.stop_error is not None:
                raise ports.stop_error
        finally:
            ports.finished.set()

    def wait(_path: Path, kind: str, *, timeout: float) -> tuple[stop_probe.WindowsFixtureEvent, ...]:
        assert timeout in {8, 12}
        assert ports.entered.wait(5)
        if ports.wait_error is not None:
            raise ports.wait_error
        return ({"at_ns": 1, "kind": kind, "pid": 1, "start": "1"},)

    def release(_root: Path, _process: stop_probe.WindowsFixtureEvent) -> None:
        if ports.release_error is not None:
            raise ports.release_error
        if ports.wait_error is None:
            ports.release.set()

    def cleanup(_name: str, _identity: stop_probe.WindowsTaskXmlShape, _root: Path, _path: Path) -> None:
        assert ports.finished.is_set()
        ports.cleanups += 1

    monkeypatch.setattr(stop_probe, "WindowsRuntimeEndpoint", endpoint)
    monkeypatch.setattr(stop_probe, "require_windows_fixture_root", lambda root: root)
    monkeypatch.setattr(stop_probe, "register_windows_probe_task", register)
    monkeypatch.setattr(stop_probe, "stop_exact_windows_task", stop)
    monkeypatch.setattr(stop_probe, "wait_windows_probe_event", wait)
    monkeypatch.setattr(stop_probe, "release_windows_probe_drain", release)
    monkeypatch.setattr(stop_probe, "cleanup_windows_probe_task", cleanup)
    return ports


@pytest.mark.parametrize("release_fails", [False, True])
@pytest.mark.parametrize("terminal", ["success", "error", "cancel"])
def test_probe_failure_retains_original_stop_until_joined_before_cleanup(
    probe_ports: _ProbePorts, tmp_path: Path, release_fails: bool, terminal: str
) -> None:
    """A failed observation cannot abandon Stop or dispatch a concurrent cleanup Stop."""
    ports = probe_ports
    primary = AssertionError("controlled missing drain event")
    ports.wait_error = primary
    ports.release_error = OSError("controlled release sentinel failure") if release_fails else None
    ports.stop_error = (
        asyncio.CancelledError("controlled callback cancellation")
        if terminal == "cancel"
        else RuntimeError("controlled callback failure")
        if terminal == "error"
        else None
    )
    owner: stop_probe.WindowsProbeTaskCleanup | None = None
    call: stop_probe.WindowsSchedulerCall | None = None
    prior = stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get()
    try:
        with (
            pytest.raises(AssertionError) as caught,
            stop_probe.registered_windows_probe_task(
                root=tmp_path, scenario="graceful", pythonw=Path(sys.executable), owner_sid="S-1-5-21-1-2-3-1001"
            ) as (name, identity, events),
        ):
            owner = stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get()
            assert owner is not None
            owner.settlement_seconds = 0
            stop_probe.stop_windows_probe_and_release_drain(
                name, identity, tmp_path, events, {"at_ns": 1, "kind": "window_ready", "pid": 1, "start": "1"}
            )
        assert caught.value is primary
        assert owner is not None
        call = owner.stop_call
        assert call is not None and call.thread.is_alive()
        assert ports.stops == 1 and ports.cleanups == 0
        assert stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get() is prior
        retained = primary.__dict__["async_cleanup_error"]
        assert isinstance(retained, AsyncResourceCleanupError)
        assert primary.__dict__["cleanup_error"] is retained
        assert retained.resources == (owner,)
        with pytest.raises(RuntimeError, match="already owned or retiring"):
            owner.start_stop()
        if ports.release_error is not None:

            def contains(error: BaseException) -> bool:
                return error is ports.release_error or (
                    isinstance(error, BaseExceptionGroup) and any(contains(child) for child in error.exceptions)
                )

            assert retained.__cause__ is not None and contains(retained.__cause__)
        ports.release.set()
        call.thread.join(timeout=5)
        assert not call.thread.is_alive() and ports.finished.is_set()
        if ports.stop_error is not None:
            with pytest.raises(AsyncResourceCleanupError) as failed:
                asyncio.run(retained.retry_cleanup())
            assert failed.value.__cause__ is ports.stop_error
            assert failed.value.resources == (owner,)
            assert owner.stop_call is None and ports.cleanups == 0
            retained = failed.value
        asyncio.run(retained.retry_cleanup())
        assert owner.released and owner.stop_call is None and owner.cleanup_call is None
        assert ports.stops == 1 and ports.cleanups == 1
        asyncio.run(retained.retry_cleanup())
        assert ports.stops == 1 and ports.cleanups == 1
    finally:
        ports.release.set()
        if owner is not None:
            if owner.stop_call is not None:
                owner.stop_call.thread.join(timeout=5)
            asyncio.run(
                close_async_resources(owner, task_name="controlled-probe-cleanup", primary_error=sys.exception())
            )


def test_probe_normal_stop_joins_before_registered_task_cleanup(probe_ports: _ProbePorts, tmp_path: Path) -> None:
    """Normal drain still returns its original events and retires the same task."""
    prior = stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get()
    with stop_probe.registered_windows_probe_task(
        root=tmp_path, scenario="graceful", pythonw=Path(sys.executable), owner_sid="S-1-5-21-1-2-3-1001"
    ) as (name, identity, events):
        owner = stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get()
        assert owner is not None
        result = stop_probe.stop_windows_probe_and_release_drain(
            name, identity, tmp_path, events, {"at_ns": 1, "kind": "window_ready", "pid": 1, "start": "1"}
        )
        assert result == ({"at_ns": 1, "kind": "drain_completed", "pid": 1, "start": "1"},)
        assert owner.stop_call is None
        assert probe_ports.stops == 1 and probe_ports.cleanups == 0
    assert owner.released and probe_ports.cleanups == 1
    assert stop_probe.WINDOWS_PROBE_TASK_CLEANUP.get() is prior


@pytest.mark.parametrize(
    "interruption", [KeyboardInterrupt("controlled interruption"), asyncio.CancelledError("caller")]
)
def test_probe_settlement_preserves_caller_interruption_after_callback_finished(
    probe_ports: _ProbePorts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: BaseException
) -> None:
    """A concurrent successful callback cannot erase an unrelated waiting caller's error."""
    owner = stop_probe.WindowsProbeTaskCleanup("controlled", ("tag", "", (), ()), tmp_path, tmp_path / "events")
    probe_ports.release.set()
    owner.start_stop()
    call = owner.stop_call
    assert call is not None
    call.thread.join(timeout=5)
    assert not call.thread.is_alive() and call.result.done()
    joins: list[float | None] = []
    original_join = call.thread.join

    def interrupted(*, timeout: float) -> BaseException | None:
        raise interruption

    def join(timeout: float | None = None) -> None:
        joins.append(timeout)
        original_join(timeout)

    with monkeypatch.context() as scheduling:
        scheduling.setattr(call.result, "exception", interrupted)
        scheduling.setattr(call.thread, "join", join)
        with pytest.raises(type(interruption)) as caught:
            owner.settle_stop()
    assert caught.value is interruption
    assert len(joins) == 1
    assert owner.stop_call is call
    owner.settle_stop()
    assert owner.stop_call is None
    assert probe_ports.stops == 1
    asyncio.run(owner.close())
    assert owner.released and probe_ports.cleanups == 1


@pytest.mark.parametrize("failed_stop", [False, True])
def test_installed_task_cleanup_joins_original_stop_after_registration_disappears(
    monkeypatch: pytest.MonkeyPatch, failed_stop: bool
) -> None:
    """A missing registration cannot discard its still-running original COM call."""
    entered, release = Event(), Event()
    stops: list[None] = []
    failure = RuntimeError("controlled native stop failure")

    def stop() -> None:
        stops.append(None)
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("controlled stop was not released")
        if failed_stop:
            raise failure

    binding = RuntimeServiceBinding(
        executable="C:/test/runtime.exe",
        storage_root="C:/test/storage",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001",
        product_version="test",
    )
    owner = stop_probe.WindowsInstalledTaskCleanup("controlled", binding)
    owner.adopted = True
    call = stop_probe.WindowsSchedulerCall(stop)
    owner.pending_stop = call
    monkeypatch.setattr(stop_probe, "installed_windows_task_identity", lambda *args, **kwargs: None)
    call.start()

    async def exercise() -> None:
        try:
            assert await asyncio.to_thread(entered.wait, timeout=2)
            closing = asyncio.create_task(
                close_async_resources(owner, task_name="controlled-installed-task-close", primary_error=None)
            )
            await asyncio.sleep(0)
            assert owner.pending_stop is call and not owner.released
            assert call.thread.is_alive() and not call.result.done()
            release.set()
            if failed_stop:
                with pytest.raises(AsyncResourceCleanupError) as caught:
                    await closing
                assert caught.value.resources == (owner,)
                assert caught.value.__cause__ is failure
                assert owner.pending_stop is None and not owner.released
                assert not call.thread.is_alive()
                await caught.value.retry_cleanup()
                await caught.value.retry_cleanup()
            else:
                await closing
            assert owner.released and owner.pending_stop is None
            assert not call.thread.is_alive() and len(stops) == 1
        finally:
            release.set()
            await close_async_resources(owner, task_name="controlled-installed-task-finally")

    asyncio.run(exercise())


def test_installed_task_cleanup_retries_only_transport_after_native_retirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit native ports expose post-delete failure without replaying retired work."""

    class ProcessPort:
        def __init__(self) -> None:
            self.closed = False
            self.waits = 0
            self.closes = 0

        def wait(self, *, timeout: float) -> int:
            assert timeout >= 0 and not self.closed
            self.waits += 1
            return 0

        def close(self) -> None:
            self.closes += 1
            assert not self.closed
            self.closed = True

    class ConnectionPort:
        def __init__(self) -> None:
            self.closes = 0

        def close(self) -> None:
            self.closes += 1
            if self.closes == 1:
                raise failure

    failure = OSError("controlled connection close failure")
    process, connection = ProcessPort(), ConnectionPort()
    physical_preparations: list[None] = []
    queries: list[None] = []
    deletions: list[None] = []
    identity = ("Task", "", (), ())

    async def prepared() -> None:
        physical_preparations.append(None)

    def lookup(*args, **kwargs):
        queries.append(None)
        return identity

    binding = RuntimeServiceBinding(
        executable="C:/test/runtime.exe",
        storage_root="C:/test/storage",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001",
        product_version="test",
    )
    owner = stop_probe.WindowsInstalledTaskCleanup("controlled", binding)
    owner.adopted = True
    owner.launch_possible = True
    owner.runtime = cast(stop_probe.InstalledWindowsRuntimeTask, SimpleNamespace(prepare_physical_cleanup=prepared))
    owner.processes.append(cast(WindowsOwnedProcess, process))
    process_owner = RuntimeTransportCleanup(process)
    connection_owner = RuntimeTransportCleanup(connection)
    owner.transports.extend((process_owner, connection_owner))
    monkeypatch.setattr(stop_probe, "installed_windows_task_identity", lookup)
    monkeypatch.setattr(stop_probe, "exact_windows_task_state", lambda *args: 3)
    monkeypatch.setattr(stop_probe, "delete_exact_windows_task", lambda *args: deletions.append(None))

    async def exercise() -> None:
        with pytest.raises(AsyncResourceCleanupError) as caught:
            await close_async_resources(owner, task_name="controlled-post-delete-release", primary_error=None)
        assert caught.value.resources == (owner,)
        assert isinstance(caught.value.__cause__, AsyncResourceCleanupError)
        assert caught.value.__cause__.resources == (connection_owner,)
        assert caught.value.__cause__.__cause__ is failure
        assert process_owner.released and not connection_owner.released
        assert process.waits == 1 and process.closes == 1 and connection.closes == 1
        assert len(deletions) == 1 and len(queries) == 1 and len(physical_preparations) == 1
        assert not owner.released
        await caught.value.retry_cleanup()
        await caught.value.retry_cleanup()
        assert owner.released and connection_owner.released
        assert process.waits == 1 and process.closes == 1 and connection.closes == 2
        assert len(deletions) == 1 and len(queries) == 1 and len(physical_preparations) == 1

    asyncio.run(exercise())


def test_installed_task_cleanup_refuses_delete_without_possible_launch_physical_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An uncertain CLI start cannot turn a missing physical witness into completion."""
    binding = RuntimeServiceBinding(
        executable="C:/test/runtime.exe",
        storage_root="C:/test/storage",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001",
        product_version="test",
    )
    owner = stop_probe.WindowsInstalledTaskCleanup("controlled", binding)
    owner.adopted = True
    owner.launch_possible = True
    deletions: list[None] = []
    monkeypatch.setattr(stop_probe, "delete_exact_windows_task", lambda *args: deletions.append(None))
    primary = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    async def exercise() -> None:
        await close_async_resources(owner, task_name="controlled-uncertain-launch", primary_error=primary)
        retained = primary.__dict__.get("async_cleanup_error")
        assert isinstance(retained, AsyncResourceCleanupError)
        assert retained.resources == (owner,)
        assert isinstance(retained.__cause__, RuntimeError)
        assert not owner.released and deletions == []
        with pytest.raises(AsyncResourceCleanupError) as retried:
            await retained.retry_cleanup()
        assert retried.value.resources == (owner,)
        assert not owner.released and deletions == []

    asyncio.run(exercise())
