"""Native Task Scheduler parsing and read-only capability checks; no task install."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Protocol, cast

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.core.async_cleanup import await_cancellation_complete

from .. import windows_manager as subject
from ..service_definitions import windows_task_xml
from ..windows import WindowsRuntimeEndpoint
from ..windows_manager import WindowsTaskManager, windows_task_binding_matches

pytestmark = pytest.mark.hex_outbound_adapter


class _TaskSettings(Protocol):
    AllowHardTerminate: bool


class _TaskDefinition(Protocol):
    XmlText: str
    Settings: _TaskSettings


class _TaskDefinitionService(Protocol):
    Connect: Callable[[], None]
    NewTask: Callable[[int], _TaskDefinition]


def _binding(root: Path) -> RuntimeServiceBinding:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)
    try:
        sid, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
        owner = win32security.ConvertSidToStringSid(sid)
    finally:
        win32api.CloseHandle(token)
    return RuntimeServiceBinding(
        executable=str(Path(sys.executable).resolve()),
        storage_root=str(root.resolve()),
        storage_identity=WindowsRuntimeEndpoint(storage_root=root).storage_identity,
        os_owner_id=owner,
        product_version="synthetic-cohort",
    )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler COM parser")
def test_native_scheduler_accepts_in_memory_definition_without_registration(tmp_path: Path, enabled: bool) -> None:
    import pythoncom
    import win32com.client

    binding = _binding(tmp_path)
    pythoncom.CoInitialize()
    try:
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        definition = service.NewTask(0)
        definition.XmlText = windows_task_xml(binding, login_autostart=enabled)
        assert windows_task_binding_matches(definition.XmlText, binding, login_autostart=enabled)
        assert definition.Principal.LogonType == 3
        assert definition.Principal.RunLevel == 0
        assert definition.Triggers.Count == int(enabled)
        assert definition.Actions.Count == 1
    finally:
        definition = None
        service = None
        pythoncom.CoUninitialize()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler COM parser")
async def test_available_manager_is_not_provisioning_or_unattended_authorization(tmp_path: Path) -> None:
    # The unique test-owned storage root has never been registered. This query
    # cannot enumerate, edit or stop another installed task.
    manager = WindowsTaskManager(_binding(tmp_path))
    inspection = await manager.inspect()
    assert inspection.available
    assert not inspection.provisioned
    assert not inspection.binding_matches
    assert not inspection.login_autostart
    with pytest.raises(RuntimeRefusalError) as caught:
        await manager.start()
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    await manager.stop()
    assert not (await manager.inspect()).provisioned


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler COM parser")
def test_native_scheduler_explicit_hard_termination_policy_change_refuses(tmp_path: Path) -> None:
    """Native default omission cannot hide an explicit changed stop policy."""
    import pythoncom
    import win32com.client

    binding = _binding(tmp_path)
    pythoncom.CoInitialize()
    service: _TaskDefinitionService | None = None
    definition: _TaskDefinition | None = None
    try:
        service = cast(_TaskDefinitionService, win32com.client.Dispatch("Schedule.Service"))
        service.Connect()
        definition = service.NewTask(0)
        definition.XmlText = windows_task_xml(binding, login_autostart=False)
        assert windows_task_binding_matches(definition.XmlText, binding, login_autostart=False)
        definition.Settings.AllowHardTerminate = False
        assert not windows_task_binding_matches(definition.XmlText, binding, login_autostart=False)
    finally:
        definition = None
        service = None
        pythoncom.CoUninitialize()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("native_failure", ["none", "refusal", "cancelled"])
async def test_cancelled_configuration_settles_once_and_retains_native_failure(
    monkeypatch: pytest.MonkeyPatch, native_failure: str
) -> None:
    """Cancellation waits for actual registration and retains its failure."""
    binding = RuntimeServiceBinding(
        executable="C:/synthetic/cadrumo-runtime.exe",
        storage_root="C:/synthetic/storage",
        storage_identity="a" * 64,
        os_owner_id="S-1-5-21-123-456-789-1001",
        product_version="synthetic-cohort",
    )
    monkeypatch.setattr(
        subject,
        "WindowsRuntimeEndpoint",
        lambda **_kwargs: SimpleNamespace(os_owner_id=binding.os_owner_id, storage_identity=binding.storage_identity),
    )
    manager = WindowsTaskManager(binding)
    entered, release, settled = Event(), Event(), Event()
    secondary = (
        asyncio.CancelledError("native configuration cancelled")
        if native_failure == "cancelled"
        else RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
    )
    registration_calls: list[str] = []
    task = SimpleNamespace(Xml="", Enabled=True, State=3)
    registered = False

    def register(
        _name: str,
        xml: str,
        _flags: int,
        _owner: str,
        _password: None,
        _logon: int,
        _security: str | None,
    ) -> object:
        nonlocal registered
        registration_calls.append(xml)
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError("configuration release barrier timed out")
            task.Xml = xml
            registered = True
            if native_failure != "none":
                raise secondary
            return task
        finally:
            settled.set()

    folder = SimpleNamespace(RegisterTask=register)
    # Only native lookup and the COM thread boundary are synthetic; the real
    # configure operation authors, registers and verifies the task definition.
    monkeypatch.setattr(manager, "_find", lambda _folder: task if registered else None)
    monkeypatch.setattr(subject, "_scheduler_call", lambda operation: operation(folder))
    running = asyncio.create_task(manager.configure(login_autostart=True))
    marker = object()
    detector_primary: BaseException | None = None
    terminal: BaseException | None = None

    async def settle_configuration() -> BaseException | None:
        try:
            await running
        except BaseException as error:
            return error
        return None

    try:
        assert await asyncio.to_thread(entered.wait, 5)
        running.cancel(marker)
        await asyncio.sleep(0)
        assert not running.done()
        running.cancel("later cancellation")
        await asyncio.sleep(0)
        assert not running.done()
    except BaseException as error:
        detector_primary = error
        raise
    finally:
        release.set()
        try:
            terminal = await asyncio.wait_for(
                await_cancellation_complete(settle_configuration(), task_name="windows-manager-detector-settlement"),
                timeout=10,
            )
        except BaseException as error:
            if detector_primary is None:
                raise
            detector_primary.__dict__["cleanup_error"] = error
            detector_primary.add_note("Configuration detector settlement also failed")
    assert running.done()
    assert isinstance(terminal, asyncio.CancelledError)
    assert terminal.args == (marker,)
    assert terminal.args[0] is marker
    assert settled.is_set()
    assert len(registration_calls) == 1
    assert registered
    assert windows_task_binding_matches(registration_calls[0], binding, login_autostart=True)
    if native_failure != "none":
        assert terminal.__dict__["cleanup_error"] is secondary
        assert terminal.__cause__ is secondary
    else:
        assert "cleanup_error" not in terminal.__dict__
        assert terminal.__cause__ is None
    assert (await manager.inspect()).binding_matches
    assert len(registration_calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("native_cancelled", [False, True])
async def test_configuration_preserves_exact_terminal_native_failure(
    monkeypatch: pytest.MonkeyPatch, native_cancelled: bool
) -> None:
    """A terminal native cancellation is not mistaken for caller cancellation."""
    binding = RuntimeServiceBinding(
        executable="C:/synthetic/cadrumo-runtime.exe",
        storage_root="C:/synthetic/storage",
        storage_identity="a" * 64,
        os_owner_id="S-1-5-21-123-456-789-1001",
        product_version="synthetic-cohort",
    )
    monkeypatch.setattr(
        subject,
        "WindowsRuntimeEndpoint",
        lambda **_kwargs: SimpleNamespace(os_owner_id=binding.os_owner_id, storage_identity=binding.storage_identity),
    )
    manager = WindowsTaskManager(binding)
    primary = (
        asyncio.CancelledError("native terminal cancellation")
        if native_cancelled
        else RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
    )
    attempts: list[object] = []

    def fail(_operation: object) -> None:
        attempts.append(_operation)
        raise primary

    monkeypatch.setattr(subject, "_scheduler_call", fail)
    with pytest.raises(type(primary)) as caught:
        await manager.configure(login_autostart=True)
    assert caught.value is primary
    assert len(attempts) == 1
