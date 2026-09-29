"""Task Scheduler control of one exactly bound interactive-token user task."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Event
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
from .windows import WindowsRuntimeEndpoint
from .windows_task_process import task_engine_owns_process

_XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
_MISSING = {0x80070002, 0x8004130F}


class _RunningTask(Protocol):
    EnginePID: int
    Stop: Callable[[int], None]


class _RunningTasks(Protocol):
    Count: int
    Item: Callable[[int], _RunningTask]


class _RegisteredTask(Protocol):
    Xml: str
    State: int
    Enabled: bool

    Run: Callable[[object], object]
    Stop: Callable[[int], None]
    GetInstances: Callable[[int], _RunningTasks]


class _TaskFolder(Protocol):
    GetTask: Callable[[str], _RegisteredTask]
    RegisterTask: Callable[[str, str, int, str, None, int, str | None], _RegisteredTask]


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
    """Control one bound task; provisioning requires an explicit configure call."""

    def __init__(self, binding: RuntimeServiceBinding) -> None:
        """Bind management to the native OS owner and stable storage-root name."""
        endpoint = WindowsRuntimeEndpoint(storage_root=Path(binding.storage_root))
        if binding.os_owner_id != endpoint.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
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
            arguments = cast(tuple[object, ...], error.args)
            hresult = arguments[0] if arguments else None
            detail = arguments[2] if len(arguments) > 2 else None
            if hresult == -2147352567 and isinstance(detail, tuple):
                details = cast(tuple[object, ...], detail)
                if len(details) == 6:
                    hresult = details[5]
            if isinstance(hresult, int) and hresult & 0xFFFFFFFF in _MISSING:
                return None
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    def _autostart(self, task: _RegisteredTask, *, xml: str | None = None) -> bool | None:
        if not task.Enabled:
            return None
        definition = task.Xml if xml is None else xml
        for enabled in (False, True):
            if windows_task_binding_matches(definition, self._binding, login_autostart=enabled):
                return enabled
        return None

    def _task_inspection(self, task: _RegisteredTask) -> RuntimeManagerInspection:
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

    async def inspect(self) -> RuntimeManagerInspection:
        """Distinguish an available scheduler from missing or foreign provisioning."""

        def inspect_task(folder: _TaskFolder) -> RuntimeManagerInspection:
            task = self._find(folder)
            if task is None:
                return self._inspection(available=True)
            return self._task_inspection(task)

        try:
            return await asyncio.to_thread(lambda: _scheduler_call(inspect_task))
        except RuntimeRefusalError:
            return self._inspection(available=False)

    async def configure(self, *, login_autostart: bool) -> RuntimeManagerInspection:
        """Provision or change only this owner's exact task, without starting it.

        The scheduler call and final read remain on the same initialized COM
        thread. A cancelled caller waits for that thread to finish so it cannot
        mistake an in-flight registration for a rolled-back change.
        """

        def configure_task(folder: _TaskFolder) -> RuntimeManagerInspection:
            current = self._find(folder)
            if current is None:
                # TASK_CREATE refuses a concurrent task occupying the same name.
                flags = 0x2
                xml = windows_task_xml(self._binding, login_autostart=login_autostart)
                # SYSTEM must retain access for the scheduler itself. The task
                # owner receives access only under the exact native SID.
                sddl: str | None = f"D:P(A;;GA;;;SY)(A;;GA;;;{self._binding.os_owner_id})"
            else:
                current_xml = current.Xml
                current_autostart = self._autostart(current, xml=current_xml)
                if current_autostart is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
                if current_autostart is login_autostart:
                    return self._task_inspection(current)
                # Preserve accepted registration metadata and all other XML.
                root = fromstring(current_xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                triggers = root.find(_XML_NAMESPACE + "Triggers")
                if triggers is not None:
                    root.remove(triggers)
                if login_autostart:
                    triggers = ElementTree.Element(_XML_NAMESPACE + "Triggers")
                    trigger = ElementTree.SubElement(triggers, _XML_NAMESPACE + "LogonTrigger")
                    ElementTree.SubElement(trigger, _XML_NAMESPACE + "Enabled").text = "true"
                    ElementTree.SubElement(trigger, _XML_NAMESPACE + "UserId").text = self._binding.os_owner_id
                    principals = root.find(_XML_NAMESPACE + "Principals")
                    if principals is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
                    root.insert(list(root).index(principals), triggers)
                xml = ElementTree.tostring(root, encoding="unicode")
                if not windows_task_binding_matches(xml, self._binding, login_autostart=login_autostart):
                    raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
                # TASK_UPDATE refuses disappearance; DONT_ADD_PRINCIPAL_ACE
                # preserves the existing task ACL when its principal is stable.
                flags = 0x4 | 0x10
                sddl = None

            # Interactive-token logon requires an already logged-in owner and
            # stores no Windows password. No Run call follows registration.
            folder.RegisterTask(self._name, xml, flags, self._binding.os_owner_id, None, 3, sddl)
            observed = self._find(folder)
            if observed is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            result = self._task_inspection(observed)
            if not result.binding_matches or result.login_autostart is not login_autostart:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            return result

        operation = asyncio.create_task(asyncio.to_thread(_scheduler_call, configure_task))
        cancelled = False
        while True:
            try:
                await asyncio.shield(operation)
                break
            except asyncio.CancelledError:
                cancelled = True
                if operation.done():
                    break
        if cancelled:
            # Retrieve any native failure to avoid an unobserved task exception;
            # cancellation never asserts that registration was rolled back.
            if not operation.cancelled():
                operation.exception()
            raise asyncio.CancelledError
        result = operation.result()
        if not isinstance(result, RuntimeManagerInspection):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return result

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

    def stop_current_process(self, submitted: Event) -> None:
        """Ask the exact running instance to stop, preserving task triggers.

        Called on a dedicated thread because native Stop may wait for the
        process to finish its own drain before returning.
        """

        def stop_task(folder: _TaskFolder) -> None:
            task = self._find(folder)
            if task is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            if self._autostart(task) is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            instances = task.GetInstances(0)
            if instances.Count != 1:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            instance = instances.Item(1)
            if not task_engine_owns_process(instance.EnginePID, os.getpid()):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            submitted.set()
            instance.Stop(0)

        _scheduler_call(stop_task)
