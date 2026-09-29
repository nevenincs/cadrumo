"""User-manager definitions keep explicit launch separate from login startup."""

from __future__ import annotations

import plistlib
from xml.etree import ElementTree

import pytest
from defusedxml.ElementTree import fromstring

from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding

from ..service_definitions import (
    linux_user_service,
    macos_agent_plist,
    runtime_service_arguments,
    runtime_service_name,
    windows_task_xml,
)
from ..windows_manager import windows_task_binding_matches

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


def _binding(*, windows: bool) -> RuntimeServiceBinding:
    return RuntimeServiceBinding(
        executable=r"C:\Program Files\Cadrumo\runtime.exe" if windows else "/opt/Cadrumo tools/runtime",
        storage_root=r"C:\Synthetic profile\state" if windows else "/synthetic/profile state",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001" if windows else "1001",
        product_version="2026.9-test",
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_windows_definition_keeps_demand_launch_interactive_and_unelevated(enabled: bool) -> None:
    binding = _binding(windows=True)
    xml = windows_task_xml(binding, login_autostart=enabled)
    document = fromstring(xml)
    assert windows_task_binding_matches(xml, binding, login_autostart=enabled)
    assert not windows_task_binding_matches(xml, binding, login_autostart=not enabled)
    assert (
        document.findtext(f"{_NAMESPACE}Principals/{_NAMESPACE}Principal/{_NAMESPACE}LogonType") == "InteractiveToken"
    )
    assert document.findtext(f"{_NAMESPACE}Principals/{_NAMESPACE}Principal/{_NAMESPACE}RunLevel") == "LeastPrivilege"
    assert document.findtext(f"{_NAMESPACE}Settings/{_NAMESPACE}AllowStartOnDemand") == "true"
    assert document.findtext(f"{_NAMESPACE}Settings/{_NAMESPACE}Enabled") == "true"
    assert document.findtext(f"{_NAMESPACE}Settings/{_NAMESPACE}ExecutionTimeLimit") == "PT0S"
    assert document.findtext(f"{_NAMESPACE}Actions/{_NAMESPACE}Exec/{_NAMESPACE}Command") == binding.executable


@pytest.mark.parametrize(
    "change",
    ["executable", "owner", "elevation", "extra_action", "extra_trigger", "cohort", "extra_setting", "extra_section"],
)
def test_changed_windows_deployment_is_never_controlled_as_the_expected_task(change: str) -> None:
    binding = _binding(windows=True)
    document = fromstring(windows_task_xml(binding, login_autostart=False))
    paths = {
        "executable": f"Actions/{_NAMESPACE}Exec/{_NAMESPACE}Command",
        "owner": f"Principals/{_NAMESPACE}Principal/{_NAMESPACE}UserId",
        "elevation": f"Principals/{_NAMESPACE}Principal/{_NAMESPACE}RunLevel",
        "cohort": f"RegistrationInfo/{_NAMESPACE}Version",
    }
    if change in paths:
        target = document.find(_NAMESPACE + paths[change])
        assert target is not None
        target.text = "changed"
    elif change == "extra_action":
        actions = document.find(_NAMESPACE + "Actions")
        assert actions is not None
        ElementTree.SubElement(actions, _NAMESPACE + "Exec")
    elif change == "extra_setting":
        settings = document.find(_NAMESPACE + "Settings")
        assert settings is not None
        ElementTree.SubElement(settings, _NAMESPACE + "DeleteExpiredTaskAfter").text = "PT0S"
    elif change == "extra_section":
        ElementTree.SubElement(document, _NAMESPACE + "Unexpected")
    else:
        triggers = ElementTree.SubElement(document, _NAMESPACE + "Triggers")
        ElementTree.SubElement(triggers, _NAMESPACE + "BootTrigger")
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
    )


@pytest.mark.parametrize(
    "path", [r"C:\%TEMP%\runtime.exe", r"C:\$(Arg0)\runtime.exe", r"\\server\share\runtime.exe", "relative.exe"]
)
def test_windows_expansion_or_remote_paths_refuse(path: str) -> None:
    binding = _binding(windows=True).model_copy(update={"executable": path})
    with pytest.raises(RuntimeRefusalError):
        windows_task_xml(binding, login_autostart=False)


@pytest.mark.parametrize("enabled", [False, True])
def test_macos_startup_policy_does_not_accidentally_enable_run_at_load(enabled: bool) -> None:
    binding = _binding(windows=False)
    document = plistlib.loads(macos_agent_plist(binding, login_autostart=enabled))
    assert document["ProgramArguments"] == [binding.executable, *runtime_service_arguments(binding)]
    assert document["RunAtLoad"] is enabled
    assert document["LimitLoadToSessionType"] == "Aqua"
    assert document["AbandonProcessGroup"] is False
    if not enabled:
        # SuccessfulExit itself implies RunAtLoad, even if RunAtLoad=false.
        assert document["KeepAlive"] is False


def test_linux_definition_escapes_specifiers_and_disables_environment_expansion() -> None:
    binding = _binding(windows=False).model_copy(update={"storage_root": '/synthetic/literal %n $HOME "quoted"'})
    unit = linux_user_service(binding)
    assert 'ExecStart=:"/opt/Cadrumo tools/runtime"' in unit
    assert '"/synthetic/literal %%n $HOME \\"quoted\\""' in unit
    assert "KillMode=mixed\n" in unit
    assert "Restart=on-failure\n" in unit
    assert "TimeoutStopSec=25\n" in unit
    assert "SendSIGKILL=yes\n" in unit
    assert "User=" not in unit
    assert "PAMName=" not in unit


def test_upgrades_keep_one_owner_name_and_change_the_expected_version() -> None:
    binding = _binding(windows=False)
    upgraded = binding.model_copy(update={"product_version": "next-cohort"})
    assert runtime_service_name(binding) == runtime_service_name(upgraded)
    assert runtime_service_arguments(binding) != runtime_service_arguments(upgraded)


def test_untrusted_xml_entities_refuse_without_expansion() -> None:
    xml = '<!DOCTYPE Task [<!ENTITY fake "synthetic">]><Task>&fake;</Task>'
    assert not windows_task_binding_matches(xml, _binding(windows=True), login_autostart=False)
