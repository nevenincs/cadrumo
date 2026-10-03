"""Task Scheduler control of one exactly bound interactive-token user task."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID
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
from ...core.async_cleanup import await_cancellation_complete
from .service_definitions import runtime_service_name, windows_task_xml
from .windows import WindowsRuntimeEndpoint
from .windows_task_process import task_engine_owns_process

_XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
_MISSING = {0x80070002, 0x8004130F}
# Microsoft task schema defaults which the native registered XML omits.
# Every explicit non-default value, duplicate or unknown field is retained.
_OMITTED_NATIVE_DEFAULTS = {
    "Principal": {"RunLevel": "LeastPrivilege"},
    "LogonTrigger": {"Enabled": "true"},
    "Settings": {
        "AllowHardTerminate": "true",
        "StartWhenAvailable": "false",
        "RunOnlyIfNetworkAvailable": "false",
        "AllowStartOnDemand": "true",
        "Enabled": "true",
        "RunOnlyIfIdle": "false",
        "DisallowStartOnRemoteAppSession": "false",
        "WakeToRun": "false",
        "Priority": "7",
    },
}

type _TaskXmlShape = tuple[str, str, tuple[tuple[str, str], ...], tuple[_TaskXmlShape, ...]]


class _RunningTask(Protocol):
    EnginePID: int
    InstanceGuid: str
    Path: str
    Refresh: Callable[[], None]
    Stop: Callable[[], None]


class _RunningTasks(Protocol):
    Count: int
    Item: Callable[[int], _RunningTask]


class _RegisteredTask(Protocol):
    Xml: str
    Path: str
    State: int
    Enabled: bool

    Run: Callable[[object], object]
    Stop: Callable[[int], None]


class _TaskFolder(Protocol):
    GetTask: Callable[[str], _RegisteredTask]
    RegisterTask: Callable[[str, str, int, str, None, int, str | None], _RegisteredTask]


class _TaskService(Protocol):
    Connect: Callable[[], None]
    GetFolder: Callable[[str], _TaskFolder]
    GetRunningTasks: Callable[[int], _RunningTasks]


@dataclass(frozen=True)
class WindowsTaskStopIdentity:
    """Retain one verified scheduler incarnation without retaining COM objects."""

    instance_guid: UUID
    engine_pid: int
    process_pid: int
    login_autostart: bool


def _instance_guid(instance: _RunningTask) -> UUID:
    raw = instance.InstanceGuid
    try:
        value = UUID(raw)
    except ValueError:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None
    # Task Scheduler uses the standard GUID representation, possibly braced.
    # Do not accept an empty identity or alternative UUID encodings.
    if not value.int or raw.lower() not in {str(value), "{" + str(value) + "}"}:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return value


def _scheduler_call[Result](operation: Callable[[_TaskFolder], Result]) -> Result:
    return _scheduler_service_call(lambda service: operation(service.GetFolder("\\")))


def _scheduler_service_call[Result](operation: Callable[[_TaskService], Result]) -> Result:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pythoncom
    import win32com.client

    # Never ignore RPC_E_CHANGED_MODE and subsequently uninitialize someone
    # else's apartment. No dispatch object may outlive this initialized scope.
    initialize_apartment = cast(Callable[[int], None], pythoncom.CoInitializeEx)
    try:
        initialize_apartment(pythoncom.COINIT_APARTMENTTHREADED)
    except pythoncom.com_error:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    def invoke() -> Result:
        service = cast(_TaskService, win32com.client.Dispatch("Schedule.Service"))
        service.Connect()
        return operation(service)

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


def _shape(element: ElementTree.Element) -> _TaskXmlShape:
    return (
        element.tag,
        (element.text or "") if len(element) == 0 else (element.text or "").strip(),
        tuple(sorted(element.attrib.items())),
        tuple(_shape(child) for child in element),
    )


def _definition_shape(element: ElementTree.Element) -> _TaskXmlShape:
    """Restore schema defaults and singleton-field ordering, preserving values."""
    children = [_definition_shape(child) for child in element]
    local_name = element.tag.removeprefix(_XML_NAMESPACE)
    present = {child[0] for child in children}
    for name, value in _OMITTED_NATIVE_DEFAULTS.get(local_name, {}).items():
        tag = _XML_NAMESPACE + name
        if tag not in present:
            children.append((tag, value, (), ()))
    if local_name in {"Principal", "Settings", "RestartOnFailure", "LogonTrigger"}:
        children.sort(key=lambda child: child[0])
    return (
        element.tag,
        (element.text or "").strip() if children else (element.text or ""),
        tuple(sorted(element.attrib.items())),
        tuple(children),
    )


def _native_account_identity(expected_sid: str) -> tuple[str, str] | None:
    """Resolve only the bound SID and roundtrip its trusted qualified account."""
    if sys.platform != "win32":
        return None
    import pywintypes
    import win32security

    try:
        sid = win32security.ConvertStringSidToSid(expected_sid)
        name, domain, account_type = win32security.LookupAccountSid(None, sid)
        if account_type != win32security.SidTypeUser or any(
            not value or len(value) > 256 or "\\" in value or any(ord(char) < 32 for char in value)
            for value in (name, domain)
        ):
            return None
        qualified = domain + "\\" + name
        # LookupAccountSid can resolve SIDhistory. Roundtrip only its trusted
        # returned name, never the account text from registered task XML.
        current_sid, _current_domain, current_type = win32security.LookupAccountName(None, qualified)
        if current_type != win32security.SidTypeUser:
            return None
        return qualified, win32security.ConvertSidToStringSid(current_sid)
    except (pywintypes.error, ValueError):
        return None


def _normalize_logon_trigger_owner(actual: ElementTree.Element, expected: ElementTree.Element) -> bool:
    """Accept only the exact expected SID or its verified current qualified name."""
    trigger_tag, owner_tag = _XML_NAMESPACE + "LogonTrigger", _XML_NAMESPACE + "UserId"
    if len(actual) != 1 or len(expected) != 1 or actual[0].tag != trigger_tag or expected[0].tag != trigger_tag:
        return False
    found, wanted = actual[0].findall(owner_tag), expected[0].findall(owner_tag)
    if len(found) != 1 or len(wanted) != 1:
        return False
    if any(len(owner) or owner.attrib or not owner.text for owner in (found[0], wanted[0])):
        return False
    actual_owner, expected_owner = found[0].text, wanted[0].text
    if actual_owner is None or expected_owner is None:
        return False
    if actual_owner == expected_owner:
        return True
    if actual_owner.count("\\") != 1:
        return False
    identity = _native_account_identity(expected_owner)
    if identity is None:
        return False
    qualified, current_sid = identity
    if current_sid != expected_owner or actual_owner != qualified:
        return False
    found[0].text = expected_owner
    return True


def _task_xml_definition_matches(actual_xml: str, expected_xml: str) -> bool:
    """Refuse changed identity, actions, triggers, policy or ambiguous XML.

    Native XML omits documented defaults and reorders singleton policy fields.
    Restore those defaults before comparison; engine and non-default settings
    remain exact. Registration metadata may include only the exact protected
    SYSTEM/owner descriptor supplied by canonical provisioning and inert facts.
    """
    if len(actual_xml) > 256 * 1024 or len(expected_xml) > 256 * 1024:
        return False
    try:
        actual = fromstring(actual_xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        expected = fromstring(expected_xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
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
            if len(found) > 1 or (found and (len(found[0]) or found[0].attrib or (found[0].text or "").strip())):
                return False
        elif len(found) != 1:
            return False
        else:
            if section == "Triggers" and len(wanted) > 0 and not _normalize_logon_trigger_owner(found[0], wanted):
                return False
            if _definition_shape(found[0]) != _definition_shape(wanted):
                return False
    registrations = actual.findall(_XML_NAMESPACE + "RegistrationInfo")
    wanted_registration = expected.find(_XML_NAMESPACE + "RegistrationInfo")
    if len(registrations) != 1 or wanted_registration is None:
        return False
    registration = registrations[0]
    if (
        registration.attrib != wanted_registration.attrib
        or (registration.text or "").strip() != (wanted_registration.text or "").strip()
    ):
        return False
    required = {item.tag: item for item in wanted_registration}
    metadata = {_XML_NAMESPACE + name for name in ("Author", "Date", "Description", "Documentation", "Source")}
    seen: set[str] = set()
    for item in registration:
        if item.tag in seen:
            return False
        seen.add(item.tag)
        if item.tag == _XML_NAMESPACE + "SecurityDescriptor":
            owners = expected.findall(f"{_XML_NAMESPACE}Principals/{_XML_NAMESPACE}Principal/{_XML_NAMESPACE}UserId")
            if len(owners) != 1 or not owners[0].text:
                return False
            intended = f"D:P(A;;GA;;;SY)(A;;GA;;;{owners[0].text})"
            if len(item) or item.attrib or item.text != intended:
                return False
        elif item.tag in required:
            if _shape(item) != _shape(required[item.tag]):
                return False
        elif item.tag not in metadata or len(item) or item.attrib:
            return False
    return required.keys() <= seen


def windows_task_binding_matches(xml: str, binding: RuntimeServiceBinding, *, login_autostart: bool) -> bool:
    """Compare native task semantics against the exact canonical binding."""
    return _task_xml_definition_matches(xml, windows_task_xml(binding, login_autostart=login_autostart))


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

        failures: list[BaseException] = []

        def configure_outcome() -> RuntimeManagerInspection | None:
            # Carry native terminal cancellation as a value across the Task
            # boundary; caller cancellation still waits for registration.
            try:
                return _scheduler_call(configure_task)
            except BaseException as error:
                failures.append(error)
                return None

        try:
            result = await await_cancellation_complete(
                asyncio.to_thread(configure_outcome),
                task_name="windows-task-manager-configure",
            )
        except asyncio.CancelledError as primary:
            if failures:

                async def failed_configuration() -> None:
                    raise failures[0]

                # Registration has already settled. Retain its exact failure
                # on the original cancellation without replaying native work.
                await await_cancellation_complete(
                    failed_configuration(),
                    task_name="windows-task-manager-configure-outcome",
                    cancellation=primary,
                )
            raise
        if failures:
            raise failures[0]
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

    def prepare_current_process_stop(self) -> WindowsTaskStopIdentity:
        """Verify this running task without stopping it or changing its triggers."""

        def prepare_task(service: _TaskService) -> WindowsTaskStopIdentity:
            folder = service.GetFolder("\\")
            task = self._find(folder)
            if task is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            autostart = self._autostart(task)
            if autostart is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            instance = self._running_instance(service, task)
            guid = _instance_guid(instance)
            engine_pid = instance.EnginePID
            process_pid = os.getpid()
            if not task_engine_owns_process(engine_pid, process_pid):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            verified = self._find(folder)
            if verified is None or self._autostart(verified) is not autostart:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            return WindowsTaskStopIdentity(guid, engine_pid, process_pid, autostart)

        return _scheduler_service_call(prepare_task)

    def _running_instance(self, service: _TaskService, task: _RegisteredTask) -> _RunningTask:
        """Select this hidden task without relying on filtered GetInstances results."""
        expected_path = "\\" + self._name
        if task.Path != expected_path:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        instances = service.GetRunningTasks(1)  # TASK_ENUM_HIDDEN, with native caller access checks.
        count = instances.Count
        if type(count) is not int or not 0 <= count <= 4096:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        matched: _RunningTask | None = None
        for index in range(1, count + 1):
            candidate = instances.Item(index)
            if candidate.Path != expected_path:
                continue
            candidate.Refresh()
            if candidate.Path != expected_path or matched is not None:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            matched = candidate
        if matched is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return matched

    def finalize_current_process_stop(self, identity: WindowsTaskStopIdentity) -> None:
        """Stop only the freshly reverified prepared instance after application drain.

        Args:
            identity: Exact native incarnation retained during preparation.

        The running-instance Stop method takes no reserved flags. Its native
        call may terminate this process; the caller retains its shutdown
        watchdog and listener ownership until this boundary settles.
        """

        def stop_task(service: _TaskService) -> None:
            folder = service.GetFolder("\\")
            task = self._find(folder)
            if task is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            autostart = self._autostart(task)
            if autostart is None or autostart is not identity.login_autostart:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            instance = self._running_instance(service, task)
            guid = _instance_guid(instance)
            engine_pid = instance.EnginePID
            process_pid = os.getpid()
            if (
                guid != identity.instance_guid
                or engine_pid != identity.engine_pid
                or process_pid != identity.process_pid
                or not task_engine_owns_process(engine_pid, process_pid)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            verified = self._find(folder)
            if verified is None or self._autostart(verified) is not identity.login_autostart:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            instance.Stop()

        _scheduler_service_call(stop_task)
