"""Exact, nonsecret per-user launch definitions for supported native managers."""

from __future__ import annotations

import plistlib
import re
import subprocess
from pathlib import PurePosixPath, PureWindowsPath
from xml.etree import ElementTree

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import RuntimeServiceBinding

_TASK_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def runtime_service_name(binding: RuntimeServiceBinding) -> str:
    """Use one stable name across version changes for the same owner/root."""
    return "cadrumo-runtime-" + binding.storage_identity


def runtime_service_arguments(binding: RuntimeServiceBinding) -> tuple[str, ...]:
    """Bind the future process explicitly; no authority or credential is passed."""
    return (
        "--storage-root",
        binding.storage_root,
        "--storage-identity",
        binding.storage_identity,
        "--expected-version",
        binding.product_version,
        "--managed-session",
    )


def _validate_paths(binding: RuntimeServiceBinding, *, windows: bool) -> None:
    for value in (binding.executable, binding.storage_root):
        if any(ord(character) < 32 for character in value):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        path = PureWindowsPath(value) if windows else PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if windows and (path.drive.startswith("\\") or "%" in value or "$(" in value):
            # Task Scheduler expands environment and task parameters even in
            # quoted fields. Reject ambiguous literal paths rather than bind
            # a different executable/root. Network deployment is unsupported.
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def windows_task_xml(binding: RuntimeServiceBinding, *, login_autostart: bool) -> str:
    """Render an interactive-token task, with on-demand launch always enabled."""
    _validate_paths(binding, windows=True)
    if re.fullmatch(r"S-1-(?:[0-9]+-)+[0-9]+", binding.os_owner_id) is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    task = ElementTree.Element("Task", {"xmlns": _TASK_NAMESPACE, "version": "1.3"})

    def element(parent: ElementTree.Element, name: str, value: str) -> None:
        ElementTree.SubElement(parent, name).text = value

    registration = ElementTree.SubElement(task, "RegistrationInfo")
    element(registration, "URI", "\\" + runtime_service_name(binding))
    element(registration, "Version", binding.product_version)
    if login_autostart:
        triggers = ElementTree.SubElement(task, "Triggers")
        trigger = ElementTree.SubElement(triggers, "LogonTrigger")
        element(trigger, "Enabled", "true")
        element(trigger, "UserId", binding.os_owner_id)
    principals = ElementTree.SubElement(task, "Principals")
    principal = ElementTree.SubElement(principals, "Principal", {"id": "Owner"})
    element(principal, "UserId", binding.os_owner_id)
    element(principal, "LogonType", "InteractiveToken")
    element(principal, "RunLevel", "LeastPrivilege")
    settings = ElementTree.SubElement(task, "Settings")
    for name, value in (
        ("MultipleInstancesPolicy", "IgnoreNew"),
        ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"),
        ("AllowHardTerminate", "true"),
        ("StartWhenAvailable", "false"),
        ("RunOnlyIfNetworkAvailable", "false"),
        ("AllowStartOnDemand", "true"),
        ("Enabled", "true"),
        ("Hidden", "true"),
        ("RunOnlyIfIdle", "false"),
        ("DisallowStartOnRemoteAppSession", "false"),
        ("UseUnifiedSchedulingEngine", "false"),
        ("WakeToRun", "false"),
        ("ExecutionTimeLimit", "PT0S"),
        ("Priority", "7"),
    ):
        element(settings, name, value)
        if name == "RunOnlyIfNetworkAvailable":
            idle = ElementTree.SubElement(settings, "IdleSettings")
            element(idle, "StopOnIdleEnd", "true")
            element(idle, "RestartOnIdle", "false")
    restart = ElementTree.SubElement(settings, "RestartOnFailure")
    element(restart, "Interval", "PT1M")
    element(restart, "Count", "3")
    actions = ElementTree.SubElement(task, "Actions", {"Context": "Owner"})
    action = ElementTree.SubElement(actions, "Exec")
    element(action, "Command", binding.executable)
    element(action, "Arguments", subprocess.list2cmdline(runtime_service_arguments(binding)))
    element(action, "WorkingDirectory", binding.storage_root)
    return ElementTree.tostring(task, encoding="unicode")


def macos_agent_plist(binding: RuntimeServiceBinding, *, login_autostart: bool) -> bytes:
    """Render a GUI-session user agent without giving it unattended authority."""
    _validate_paths(binding, windows=False)
    if not binding.os_owner_id.isdecimal():
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return plistlib.dumps(
        {
            "Label": runtime_service_name(binding),
            "Program": binding.executable,
            "ProgramArguments": [binding.executable, *runtime_service_arguments(binding)],
            "WorkingDirectory": binding.storage_root,
            "LimitLoadToSessionType": "Aqua",
            "RunAtLoad": login_autostart,
            # SuccessfulExit implies RunAtLoad in launchd. Do not accidentally
            # enable startup when the operator selected on-demand only. That
            # mode has no automatic restart until an installed mechanism with
            # equivalent on-demand semantics has been proven.
            "KeepAlive": {"SuccessfulExit": False} if login_autostart else False,
            "ThrottleInterval": 60,
            "ExitTimeOut": 15,
            "AbandonProcessGroup": False,
            "Umask": 0o077,
            "StandardOutPath": "/dev/null",
            "StandardErrorPath": "/dev/null",
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )


def _systemd_argument(value: str) -> str:
    # systemd uses its own C-style quoting and % specifiers, not shell syntax.
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def linux_user_service(binding: RuntimeServiceBinding) -> str:
    """Render a user unit; enabling its target link is a separate explicit action."""
    _validate_paths(binding, windows=False)
    if not binding.os_owner_id.isdecimal():
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    if binding.storage_root != binding.storage_root.rstrip() or binding.storage_root.endswith("\\"):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    command = " ".join(_systemd_argument(value) for value in (binding.executable, *runtime_service_arguments(binding)))
    return (
        "[Unit]\nDescription=Cadrumo local runtime\n"
        "StartLimitIntervalSec=300\nStartLimitBurst=3\n"
        "[Service]\nType=exec\n"
        # ':' disables $ expansion; %% protects literal % in all paths.
        f"ExecStart=:{command}\n"
        # WorkingDirectory is a scalar path, not the ExecStart word grammar.
        f"WorkingDirectory={binding.storage_root.replace('%', '%%')}\n"
        "Restart=on-failure\nRestartSec=60\nTimeoutStopSec=15\n"
        "KillMode=control-group\nSendSIGKILL=yes\n"
        "UMask=0077\nStandardInput=null\nStandardOutput=null\nStandardError=null\n"
        "[Install]\nWantedBy=default.target\n"
    )
