"""Task Scheduler control of one exactly bound interactive-token user task."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast
from xml.etree import ElementTree

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
    RuntimeServiceBinding,
)
from .service_definitions import runtime_service_name, windows_task_xml
from .windows import WindowsRuntimeEndpoint, _current_owner_sid

_XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
_MISSING = {0x80070002, 0x8004130F}


class _RegisteredTask(Protocol):
    Xml: str
    State: int
    Enabled: bool

    Run: Callable[[object], object]
    Stop: Callable[[int], None]


class _TaskFolder(Protocol):
    GetTask: Callable[[str], _RegisteredTask]


class _TaskService(Protocol):
    Connect: Callable[[], None]
    GetFolder: Callable[[str], _TaskFolder]


def _scheduler_call[Result](operation: Callable[[_TaskFolder], Result]) -> Result:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pythoncom
    import win32com.client

    # Never ignore RPC_E_CHANGED_MODE and subsequently uninitialize someone
    # else's apartment. No dispatch object may outlive this initialized scope.
    try:
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    except pythoncom.com_error:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    def invoke() -> Result:
        service = cast(_TaskService, win32com.client.Dispatch("Schedule.Service"))
        service.Connect()
        return operation(service.GetFolder("\\"))

    refusal: RuntimeRefusalCode | None = None
    result: list[Result] = []
    try:
        try:
            result.append(invoke())
        except pythoncom.com_error:
            refusal = RuntimeRefusalCode.UNAVAILABLE
        except RuntimeRefusalError as error:
            refusal = error.reason
    finally:
        pythoncom.CoUninitialize()
    if refusal is not None:
        raise RuntimeRefusalError(refusal)
    return result[0]


def _shape(element: ElementTree.Element) -> tuple[str, str, tuple[tuple[str, str], ...], tuple[object, ...]]:
    return (
        element.tag,
        (element.text or "") if len(element) == 0 else (element.text or "").strip(),
        tuple(sorted(element.attrib.items())),
        tuple(_shape(child) for child in element),
    )


def windows_task_binding_matches(xml: str, binding: RuntimeServiceBinding, *, login_autostart: bool) -> bool:
    """Refuse changed identity, actions, triggers, policy or ambiguous XML.

    Settings include the native defaults explicitly. Only inert registration
    metadata may be added; unknown behavior and duplicate fields refuse.
    """
    if len(xml) > 256 * 1024:
        return False
    try:
        actual = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        expected = fromstring(windows_task_xml(binding, login_autostart=login_autostart))
    except (ElementTree.ParseError, DefusedXmlException):
        return False
    if actual.tag != expected.tag or actual.attrib != expected.attrib:
        return False
    allowed_sections = {
        _XML_NAMESPACE + name for name in ("Principals", "Actions", "Triggers", "Settings", "RegistrationInfo")
    }
    if any(child.tag not in allowed_sections for child in actual):
        return False
    for section in ("Principals", "Actions", "Triggers", "Settings"):
        found = actual.findall(_XML_NAMESPACE + section)
        wanted = expected.find(_XML_NAMESPACE + section)
        if wanted is None:
            if len(found) > 1 or (found and len(found[0])):
                return False
        elif len(found) != 1 or _shape(found[0]) != _shape(wanted):
            return False
    registrations = actual.findall(_XML_NAMESPACE + "RegistrationInfo")
    wanted_registration = expected.find(_XML_NAMESPACE + "RegistrationInfo")
    if len(registrations) != 1 or wanted_registration is None:
        return False
    registration = registrations[0]
    required = {item.tag: item for item in wanted_registration}
    metadata = {_XML_NAMESPACE + name for name in ("Author", "Date", "Description", "Documentation", "Source")}
    seen: set[str] = set()
    for item in registration:
        if item.tag in seen:
            return False
        seen.add(item.tag)
        if item.tag in required:
            if _shape(item) != _shape(required[item.tag]):
                return False
        elif item.tag not in metadata or len(item) or item.attrib:
            return False
    return required.keys() <= seen


class WindowsTaskManager:
    """Control a pre-provisioned task; never register or enable one implicitly."""

    def __init__(self, binding: RuntimeServiceBinding) -> None:
        """Bind management to the native OS owner and stable storage-root name."""
        if binding.os_owner_id != _current_owner_sid():
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        endpoint = WindowsRuntimeEndpoint(storage_root=Path(binding.storage_root))
        if endpoint.storage_identity != binding.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        # Validate all paths/fields even when no manager operation is attempted.
        windows_task_xml(binding, login_autostart=False)
        self._binding = binding
        self._name = runtime_service_name(binding)

    def _find(self, folder: _TaskFolder) -> _RegisteredTask | None:
        import pythoncom

        try:
            return folder.GetTask(self._name)
        except pythoncom.com_error as error:
            hresult = error.args[0] if error.args else None
            detail = error.args[2] if len(error.args) > 2 else None
            if hresult == -2147352567 and isinstance(detail, tuple) and len(detail) == 6:
                hresult = detail[5]
            if isinstance(hresult, int) and hresult & 0xFFFFFFFF in _MISSING:
                return None
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    def _autostart(self, task: _RegisteredTask) -> bool | None:
        if not task.Enabled:
            return None
        for enabled in (False, True):
            if windows_task_binding_matches(task.Xml, self._binding, login_autostart=enabled):
                return enabled
        return None

    async def inspect(self) -> RuntimeManagerInspection:
        """Distinguish an available scheduler from missing or foreign provisioning."""

        def inspect_task(folder: _TaskFolder) -> RuntimeManagerInspection:
            task = self._find(folder)
            if task is None:
                return self._inspection(available=True)
            autostart = self._autostart(task)
            state = {
                2: RuntimeManagerProcessState.STARTING,
                3: RuntimeManagerProcessState.STOPPED,
                4: RuntimeManagerProcessState.RUNNING,
            }.get(task.State, RuntimeManagerProcessState.UNKNOWN)
            return RuntimeManagerInspection(
                kind=RuntimeManagerKind.WINDOWS_TASK,
                available=True,
                provisioned=True,
                binding_matches=autostart is not None,
                login_autostart=autostart is True,
                process_state=state,
            )

        try:
            return await asyncio.to_thread(lambda: _scheduler_call(inspect_task))
        except RuntimeRefusalError:
            return self._inspection(available=False)

    @staticmethod
    def _inspection(*, available: bool) -> RuntimeManagerInspection:
        return RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=available,
            provisioned=False,
            binding_matches=False,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.UNKNOWN,
        )

    async def start(self) -> None:
        """Run only existing matching provisioning, leaving its triggers unchanged."""

        def start_task(folder: _TaskFolder) -> None:
            task = self._find(folder)
            if task is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            if self._autostart(task) is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            task.Run(None)

        await asyncio.to_thread(_scheduler_call, start_task)

    async def stop(self) -> None:
        """Stop matching provisioning only; application draining must precede this."""

        def stop_task(folder: _TaskFolder) -> None:
            task = self._find(folder)
            if task is None:
                return
            if self._autostart(task) is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            task.Stop(0)

        await asyncio.to_thread(_scheduler_call, stop_task)
