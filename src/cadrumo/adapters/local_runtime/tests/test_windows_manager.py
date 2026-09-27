"""Native Task Scheduler parsing and read-only capability checks; no task install."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding

from ..service_definitions import windows_task_xml
from ..windows import WindowsRuntimeEndpoint
from ..windows_manager import WindowsTaskManager, windows_task_binding_matches

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler COM parser"),
]


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
