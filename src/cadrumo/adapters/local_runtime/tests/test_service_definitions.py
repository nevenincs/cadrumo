"""User-manager definitions keep explicit launch separate from login startup."""

from __future__ import annotations

import plistlib
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from defusedxml.ElementTree import fromstring

from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding

from .. import windows_manager
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
# Native registered structure captured by the owning no-start metadata probe.
# Only public owner/action/cohort values are rebound to the synthetic fixture.
_REGISTERED_WINDOWS_TASK = """<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Version /><URI /></RegistrationInfo>
  <Principals><Principal id="Owner"><UserId /><LogonType>InteractiveToken</LogonType></Principal></Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Hidden>true</Hidden>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <IdleSettings><StopOnIdleEnd>true</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
  </Settings>
  <Triggers />
  <Actions Context="Owner"><Exec><Command /><Arguments /><WorkingDirectory /></Exec></Actions>
</Task>"""


def _binding(*, windows: bool) -> RuntimeServiceBinding:
    return RuntimeServiceBinding(
        executable=r"C:\Program Files\Cadrumo\runtime.exe" if windows else "/opt/Cadrumo tools/runtime",
        storage_root=r"C:\Synthetic profile\state" if windows else "/synthetic/profile state",
        storage_identity="1" * 64,
        os_owner_id="S-1-5-21-1-2-3-1001" if windows else "1001",
        product_version="2026.9-test",
    )


def _native_registered_windows_document(binding: RuntimeServiceBinding) -> ElementTree.Element:
    document = fromstring(_REGISTERED_WINDOWS_TASK)
    expected = fromstring(windows_task_xml(binding, login_autostart=False))
    for path in (
        f"RegistrationInfo/{_NAMESPACE}Version",
        f"RegistrationInfo/{_NAMESPACE}URI",
        f"Principals/{_NAMESPACE}Principal/{_NAMESPACE}UserId",
        f"Actions/{_NAMESPACE}Exec/{_NAMESPACE}Command",
        f"Actions/{_NAMESPACE}Exec/{_NAMESPACE}Arguments",
        f"Actions/{_NAMESPACE}Exec/{_NAMESPACE}WorkingDirectory",
    ):
        actual_leaf, expected_leaf = document.find(_NAMESPACE + path), expected.find(_NAMESPACE + path)
        assert actual_leaf is not None and expected_leaf is not None
        actual_leaf.text = expected_leaf.text
    return document


def test_windows_native_registered_defaults_and_order_preserve_the_exact_binding() -> None:
    """Accept captured native omission/order while retaining all behavior."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    assert windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
    )


def test_windows_native_registered_exact_protected_security_descriptor_matches() -> None:
    """Provisioning's native descriptor preserves SYSTEM and exact-owner access."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    registration = document.find(_NAMESPACE + "RegistrationInfo")
    assert registration is not None
    ElementTree.SubElement(
        registration, _NAMESPACE + "SecurityDescriptor"
    ).text = f"D:P(A;;GA;;;SY)(A;;GA;;;{binding.os_owner_id})"
    assert windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
    )


@pytest.mark.parametrize(
    "change",
    ["foreign", "broad", "unprotected", "missing_system", "reduced_access", "attribute", "nested", "duplicate"],
)
def test_windows_native_registered_changed_security_descriptor_refuses(change: str) -> None:
    """Optional native metadata cannot hide broadened or ambiguous task access."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    registration = document.find(_NAMESPACE + "RegistrationInfo")
    assert registration is not None
    descriptor = ElementTree.SubElement(registration, _NAMESPACE + "SecurityDescriptor")
    descriptor.text = f"D:P(A;;GA;;;SY)(A;;GA;;;{binding.os_owner_id})"
    if change == "foreign":
        descriptor.text = descriptor.text.replace(binding.os_owner_id, "S-1-5-21-1-2-3-1002")
    elif change == "broad":
        descriptor.text += "(A;;GA;;;WD)"
    elif change == "unprotected":
        descriptor.text = descriptor.text.replace("D:P", "D:")
    elif change == "missing_system":
        descriptor.text = descriptor.text.replace("(A;;GA;;;SY)", "")
    elif change == "reduced_access":
        descriptor.text = descriptor.text.replace("GA", "GR")
    elif change == "attribute":
        descriptor.set("unexpected", "true")
    elif change == "nested":
        ElementTree.SubElement(descriptor, _NAMESPACE + "Unexpected")
    else:
        ElementTree.SubElement(registration, _NAMESPACE + "SecurityDescriptor").text = descriptor.text
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
    )


@pytest.mark.parametrize(
    "change",
    [
        "engine",
        "owner",
        "argv",
        "hard_terminate",
        "demand_launch",
        "elevation",
        "duplicate_default",
        "duplicate_setting",
        "registration_attribute",
        "empty_trigger_attribute",
    ],
)
def test_windows_native_registered_policy_or_identity_substitution_refuses(change: str) -> None:
    """Default restoration cannot hide changed values or ambiguous XML."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    settings = document.find(_NAMESPACE + "Settings")
    assert settings is not None
    if change in {"engine", "owner", "argv"}:
        paths = {
            "engine": f"Settings/{_NAMESPACE}UseUnifiedSchedulingEngine",
            "owner": f"Principals/{_NAMESPACE}Principal/{_NAMESPACE}UserId",
            "argv": f"Actions/{_NAMESPACE}Exec/{_NAMESPACE}Arguments",
        }
        leaf = document.find(_NAMESPACE + paths[change])
        assert leaf is not None
        leaf.text = "false" if change == "engine" else "substituted"
    elif change == "elevation":
        principal = document.find(f"{_NAMESPACE}Principals/{_NAMESPACE}Principal")
        assert principal is not None
        ElementTree.SubElement(principal, _NAMESPACE + "RunLevel").text = "HighestAvailable"
    elif change == "registration_attribute":
        registration = document.find(_NAMESPACE + "RegistrationInfo")
        assert registration is not None
        registration.set("unexpected", "true")
    elif change == "empty_trigger_attribute":
        triggers = document.find(_NAMESPACE + "Triggers")
        assert triggers is not None
        triggers.set("unexpected", "true")
    elif change == "duplicate_setting":
        ElementTree.SubElement(settings, _NAMESPACE + "Hidden").text = "true"
    elif change == "duplicate_default":
        for _ in range(2):
            ElementTree.SubElement(settings, _NAMESPACE + "AllowHardTerminate").text = "true"
    else:
        field = "AllowHardTerminate" if change == "hard_terminate" else "AllowStartOnDemand"
        ElementTree.SubElement(settings, _NAMESPACE + field).text = "false"
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
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
    assert document.findtext(f"{_NAMESPACE}Settings/{_NAMESPACE}UseUnifiedSchedulingEngine") == "true"
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
    assert document["ExitTimeOut"] == 25
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


@pytest.mark.parametrize("owner_form", ["sid", "qualified"])
def test_windows_logon_trigger_native_default_and_verified_owner_match(
    monkeypatch: pytest.MonkeyPatch, owner_form: str
) -> None:
    """Native omission/order and a proved current account retain exact ownership."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    triggers = document.find(_NAMESPACE + "Triggers")
    assert triggers is not None
    trigger = ElementTree.SubElement(triggers, _NAMESPACE + "LogonTrigger")
    qualified = r"WORKSTATION\synthetic-owner"
    ElementTree.SubElement(trigger, _NAMESPACE + "UserId").text = (
        binding.os_owner_id if owner_form == "sid" else qualified
    )
    looked_up: list[str] = []

    def resolve(expected_sid: str) -> tuple[str, str]:
        looked_up.append(expected_sid)
        return qualified, binding.os_owner_id

    monkeypatch.setattr(windows_manager, "_native_account_identity", resolve)
    xml = ElementTree.tostring(document, encoding="unicode")
    assert windows_task_binding_matches(xml, binding, login_autostart=True)
    assert not windows_task_binding_matches(xml, binding, login_autostart=False)
    assert looked_up == ([] if owner_form == "sid" else [binding.os_owner_id])
    # Explicit true after UserId is also the same singleton schema meaning.
    ElementTree.SubElement(trigger, _NAMESPACE + "Enabled").text = "true"
    assert windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=True
    )


@pytest.mark.parametrize("lookup_failure", ["unresolved", "changed_sid"])
def test_windows_logon_trigger_owner_lookup_requires_exact_current_sid(
    monkeypatch: pytest.MonkeyPatch, lookup_failure: str
) -> None:
    """Unresolved accounts and SIDhistory substitution cannot authorize a trigger."""
    binding = _binding(windows=True)
    document = fromstring(windows_task_xml(binding, login_autostart=True))
    owner = document.find(f"{_NAMESPACE}Triggers/{_NAMESPACE}LogonTrigger/{_NAMESPACE}UserId")
    assert owner is not None
    qualified = r"WORKSTATION\synthetic-owner"
    owner.text = qualified
    looked_up: list[str] = []

    def resolve(expected_sid: str) -> tuple[str, str] | None:
        looked_up.append(expected_sid)
        return None if lookup_failure == "unresolved" else (qualified, "S-1-5-21-1-2-3-1002")

    monkeypatch.setattr(windows_manager, "_native_account_identity", resolve)
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=True
    )
    assert looked_up == [binding.os_owner_id]


@pytest.mark.parametrize(
    "change",
    [
        "foreign_sid",
        "foreign_qualified",
        "unqualified",
        "disabled",
        "duplicate_enabled",
        "duplicate_trigger",
        "unknown",
    ],
)
def test_windows_logon_trigger_native_normalization_keeps_refusals(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Only an exact supported singleton trigger receives native normalization."""
    binding = _binding(windows=True)
    document = fromstring(windows_task_xml(binding, login_autostart=True))
    triggers = document.find(_NAMESPACE + "Triggers")
    assert triggers is not None
    trigger = triggers[0]
    owner, enabled = trigger.find(_NAMESPACE + "UserId"), trigger.find(_NAMESPACE + "Enabled")
    assert owner is not None and enabled is not None
    qualified = r"WORKSTATION\synthetic-owner"
    owner.text = qualified
    looked_up: list[str] = []

    def resolve(expected_sid: str) -> tuple[str, str]:
        looked_up.append(expected_sid)
        return qualified, binding.os_owner_id

    monkeypatch.setattr(windows_manager, "_native_account_identity", resolve)
    if change == "foreign_sid":
        owner.text = "S-1-5-21-1-2-3-1002"
    elif change == "foreign_qualified":
        owner.text = r"FOREIGN\other-owner"
    elif change == "unqualified":
        owner.text = "synthetic-owner"
    elif change == "disabled":
        enabled.text = "false"
    elif change == "duplicate_enabled":
        ElementTree.SubElement(trigger, _NAMESPACE + "Enabled").text = "true"
    elif change == "duplicate_trigger":
        ElementTree.SubElement(triggers, _NAMESPACE + "LogonTrigger")
    else:
        ElementTree.SubElement(trigger, _NAMESPACE + "Unknown").text = "true"
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=True
    )
    assert all(expected_sid == binding.os_owner_id for expected_sid in looked_up)
    if change in {"foreign_sid", "unqualified", "duplicate_trigger"}:
        assert looked_up == []


def test_windows_logon_trigger_native_lookup_is_unavailable_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported platforms refuse alias lookup before importing native APIs."""
    monkeypatch.setattr(windows_manager, "sys", SimpleNamespace(platform="linux"))
    assert windows_manager._native_account_identity(_binding(windows=True).os_owner_id) is None


def test_windows_task_matcher_preserves_exact_empty_expected_triggers() -> None:
    """Exact empty sections stay equal, while an added trigger is refused."""
    document = fromstring(windows_task_xml(_binding(windows=True), login_autostart=False))
    triggers = ElementTree.SubElement(document, _NAMESPACE + "Triggers")
    expected = ElementTree.tostring(document, encoding="unicode")
    assert windows_manager._task_xml_definition_matches(expected, expected)
    trigger = ElementTree.SubElement(triggers, _NAMESPACE + "LogonTrigger")
    ElementTree.SubElement(trigger, _NAMESPACE + "UserId").text = _binding(windows=True).os_owner_id
    assert not windows_manager._task_xml_definition_matches(
        ElementTree.tostring(document, encoding="unicode"), expected
    )


def test_windows_native_outer_restart_policy_refuses() -> None:
    """A second native retry owner is drift from the current exact definition."""
    binding = _binding(windows=True)
    document = _native_registered_windows_document(binding)
    settings = document.find(_NAMESPACE + "Settings")
    assert settings is not None
    restart = ElementTree.SubElement(settings, _NAMESPACE + "RestartOnFailure")
    ElementTree.SubElement(restart, _NAMESPACE + "Count").text = "3"
    ElementTree.SubElement(restart, _NAMESPACE + "Interval").text = "PT1M"
    assert not windows_task_binding_matches(
        ElementTree.tostring(document, encoding="unicode"), binding, login_autostart=False
    )
