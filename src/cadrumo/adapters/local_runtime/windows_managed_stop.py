"""Prepare exact-task ownership, then finalize native stop after runtime drain."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Lock, RLock
from types import TracebackType
from typing import TYPE_CHECKING, Self, cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import RuntimeServiceBinding
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures
from ...core.hashing import reject_duplicate_json_members, reject_json_constant
from .framing import RuntimeTransportCleanup
from .windows_manager import WindowsTaskManager, WindowsTaskStopIdentity
from .windows_process import WindowsOwnedProcess
from .windows_task_process import task_engine_owns_process

if TYPE_CHECKING:
    from _win32typing import PyACL, PyHANDLE, PySECURITY_DESCRIPTOR


class WindowsManagedRuntimeStop:
    """Keep native stop separate from consent acknowledgement and private drain.

    Preparation reads exact native ownership without stopping any process.
    The server invokes finalization only after its accepted stop has drained
    application resources, while listener ownership and watchdog remain held.
    Neither phase changes persistent task provisioning or login autostart.
    """

    def __init__(self, binding: RuntimeServiceBinding, stop: Event) -> None:
        """Bind the owner task and the server's shutdown signal.

        Args:
            binding: Canonical service definition and native owner identity.
            stop: Signal set by the server after accepting stop preparation.
        """
        self._manager = WindowsTaskManager(binding)
        self._stop = stop
        self._identity: WindowsTaskStopIdentity | None = None
        self._finalized = False
        self._guard = Lock()

    def __enter__(self) -> Self:
        """Keep the lifecycle interface without creating an unrelated stop window."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, _traceback: TracebackType | None
    ) -> None:
        """Retain no native handle or COM wrapper requiring context cleanup."""

    def __call__(self) -> None:
        """Prepare exact ownership without invoking native Stop."""
        with self._guard:
            if self._identity is not None or self._finalized or self._stop.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._identity = self._manager.prepare_current_process_stop()

    def finalize(self) -> None:
        """Reverify and stop the prepared instance after the server's drain fence.

        A native refusal or uncertain failure retains the prepared identity.
        A retry must pass the complete native ownership checks again; no
        unsuccessful attempt is presented as a completed stop.
        """
        with self._guard:
            identity = self._identity
            if identity is None or self._finalized or not self._stop.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._manager.finalize_current_process_stop(identity)
            self._identity = None
            self._finalized = True


@dataclass(frozen=True)
class WindowsRuntimeLaunchIdentity:
    """Nonsecret per-launcher disposition; never profile or operation authority."""

    stop_name: str
    launcher_pid: int
    launcher_created: str
    instance_guid: str
    engine_pid: int
    login_autostart: bool

    def encode(self) -> str:
        """Encode the nonsecret native launcher coordinates."""
        return json.dumps(
            {
                "stop_name": self.stop_name,
                "launcher_pid": self.launcher_pid,
                "launcher_created": self.launcher_created,
                "instance_guid": self.instance_guid,
                "engine_pid": self.engine_pid,
                "login_autostart": self.login_autostart,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value: str) -> WindowsRuntimeLaunchIdentity:
        """Validate the exact nonsecret launcher coordinates."""
        from uuid import UUID

        if not 1 <= len(value) <= 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        try:
            decoded: object = json.loads(
                value, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
            )
            if not isinstance(decoded, dict):
                raise ValueError
            row = cast("dict[str, object]", decoded)
            if set(row) != {
                "stop_name",
                "launcher_pid",
                "launcher_created",
                "instance_guid",
                "engine_pid",
                "login_autostart",
            }:
                raise ValueError
            if (
                type(row["launcher_pid"]) is not int
                or not 0 < row["launcher_pid"] <= 0xFFFFFFFF
                or type(row["engine_pid"]) is not int
                or not 0 < row["engine_pid"] <= 0xFFFFFFFF
                or type(row["login_autostart"]) is not bool
                or not isinstance(row["launcher_created"], str)
                or not 1 <= len(row["launcher_created"]) <= 64
                or not isinstance(row["instance_guid"], str)
                or str(UUID(row["instance_guid"])) != row["instance_guid"]
                or not isinstance(row["stop_name"], str)
                or not row["stop_name"].startswith("Local\\cadrumo-runtime-stop-")
                or len(row["stop_name"]) != len("Local\\cadrumo-runtime-stop-") + 32
                or UUID(hex=row["stop_name"][-32:]).hex != row["stop_name"][-32:]
            ):
                raise ValueError
            return cls(
                stop_name=row["stop_name"],
                launcher_pid=row["launcher_pid"],
                launcher_created=row["launcher_created"],
                instance_guid=row["instance_guid"],
                engine_pid=row["engine_pid"],
                login_autostart=row["login_autostart"],
            )
        except (ValueError, TypeError, OverflowError):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None


class WindowsRuntimeStopLatch:
    """Own one noninherited, owner-only named manual-reset event."""

    def __init__(self, *, expected_owner: str, name: str, create: bool) -> None:
        """Create or open one protected owner Event and retain its handle."""
        import pywintypes
        import win32api
        import win32event
        import win32security

        self.name = name
        self._handle: int | None = None
        self._parent_owner: RuntimeTransportCleanup | None = None
        self._lock = RLock()
        self._can_wait = create
        self._cleanup = RuntimeTransportCleanup(self)
        try:
            if create:
                parse_descriptor = cast(
                    "Callable[[str, int], PySECURITY_DESCRIPTOR]",
                    win32security.ConvertStringSecurityDescriptorToSecurityDescriptor,
                )
                descriptor = parse_descriptor(f"O:{expected_owner}D:P(A;;0x001f0003;;;{expected_owner})", 1)
                attributes = pywintypes.SECURITY_ATTRIBUTES()
                attributes.SECURITY_DESCRIPTOR = descriptor
                attributes.bInheritHandle = False
                handle = win32event.CreateEvent(attributes, True, False, name)
                self._handle = handle
                already_exists = win32api.GetLastError() == 183
                if already_exists:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            else:
                open_event = cast("Callable[[int, bool, str], int]", win32event.OpenEvent)
                self._handle = open_event(0x00020002, False, name)
            read_security = cast("Callable[[int, int, int], PySECURITY_DESCRIPTOR]", win32security.GetSecurityInfo)
            description = read_security(
                self._handle,
                win32security.SE_KERNEL_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION,
            )
            read_dacl = cast("Callable[[], PyACL | None]", description.GetSecurityDescriptorDacl)
            dacl = read_dacl()
            read_control = cast("Callable[[], tuple[int, int]]", description.GetSecurityDescriptorControl)
            handle_flags = cast("Callable[[int], int]", win32api.GetHandleInformation)
            if (
                win32security.ConvertSidToStringSid(description.GetSecurityDescriptorOwner()) != expected_owner
                or not read_control()[0] & 0x1000
                or dacl is None
                or dacl.GetAceCount() != 1
                or handle_flags(self._handle) & 1
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            (kind, flags), access, sid = dacl.GetAce(0)
            if (
                kind != 0
                or flags != 0
                or access != 0x001F0003
                or win32security.ConvertSidToStringSid(sid) != expected_owner
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        except BaseException as primary:
            try:
                self._cleanup.close_now()
            except BaseException as failure:
                self._retain_failure(primary, failure)
            raise

    def _retain_failure(self, primary: BaseException, failure: BaseException) -> None:
        retained = AsyncResourceCleanupError(
            (self._cleanup,), (failure,), retry_task_name="windows-runtime-stop-latch-close", close_attempts=1
        )
        for previous in async_cleanup_failures(primary):
            retained = previous.merged_with(retained)
        primary.__dict__["async_cleanup_error"] = retained
        if isinstance(primary.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
            primary.__dict__["cleanup_error"] = retained

    def set(self) -> None:
        """Publish the intentional-stop latch before local shutdown."""
        import win32event

        with self._lock:
            if self._handle is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            win32event.SetEvent(self._handle)

    @property
    def cleanup_owner(self) -> RuntimeTransportCleanup:
        """Expose the one stable owner for canonical asynchronous settlement."""
        return self._cleanup

    def wait(self, timeout: float) -> bool:
        """Observe the retained manual-reset Event within the requested bound."""
        import math

        import win32event

        with self._lock:
            if self._handle is None or not self._can_wait or not math.isfinite(timeout) or timeout < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            result = win32event.WaitForSingleObject(self._handle, min(0xFFFFFFFE, math.ceil(timeout * 1000)))
            if result not in (win32event.WAIT_OBJECT_0, win32event.WAIT_TIMEOUT):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return result == win32event.WAIT_OBJECT_0

    def close(self) -> None:
        """Release Event and parent handles, retaining failed releases."""
        import win32api

        with self._lock:
            failures: list[BaseException] = []
            if self._handle is not None:
                try:
                    win32api.CloseHandle(self._handle)
                except BaseException as error:
                    failures.append(error)
                else:
                    self._handle = None
            if self._parent_owner is not None:
                try:
                    self._parent_owner.close_now()
                except BaseException as error:
                    failures.append(error)
                else:
                    self._parent_owner = None
            if failures:
                raise AsyncResourceCleanupError(
                    (self._cleanup,),
                    tuple(failures),
                    retry_task_name="windows-runtime-stop-latch-close",
                    close_attempts=1,
                ) from failures[0]

    def __enter__(self) -> Self:
        """Keep the acquired native latch within its owning scope."""
        return self

    def retain_parent(self, owner: RuntimeTransportCleanup) -> None:
        """Transfer the already corroborated native parent into this lifetime."""
        with self._lock:
            if (
                self._handle is None
                or self._parent_owner is not None
                or not isinstance(owner.resource, WindowsOwnedProcess)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._parent_owner = owner

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Settle native resources without replacing the body's primary error."""
        try:
            self._cleanup.close_now()
        except BaseException as failure:
            if exc is None:
                raise AsyncResourceCleanupError(
                    (self._cleanup,), (failure,), retry_task_name="windows-runtime-stop-latch-close", close_attempts=1
                ) from failure
            self._retain_failure(exc, failure)


def open_runtime_launcher_latch(binding: RuntimeServiceBinding, encoded: str) -> WindowsRuntimeStopLatch:
    """Check actual parent/task/root/version before opening nonsecret disposition."""
    import win32api
    import win32con
    import win32event
    import win32process

    process_times = cast("Callable[[int], Mapping[str, object]]", win32process.GetProcessTimes)
    identity = WindowsRuntimeLaunchIdentity.decode(encoded)
    current = WindowsTaskManager(binding).prepare_current_process_stop()
    if (
        str(current.instance_guid) != identity.instance_guid
        or current.engine_pid != identity.engine_pid
        or current.login_autostart is not identity.login_autostart
        or identity.launcher_pid == os.getpid()
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    handle = int(
        cast(
            "PyHANDLE",
            cast(
                object,
                win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, identity.launcher_pid
                ),
            ),
        ).Detach()
    )
    parent = WindowsOwnedProcess(handle=handle, pid=identity.launcher_pid)
    # The native parent handle is owned independently of event acquisition.
    owner = RuntimeTransportCleanup(parent)
    primaries: list[BaseException] = []
    transferred = False
    try:
        # This parent belongs to the same exact scheduler instance as the host;
        # the existing ancestry checker rejects stale PIDs and bounds traversal.
        if (
            win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT
            or cast(datetime, process_times(handle)["CreationTime"]).isoformat() != identity.launcher_created
            or not task_engine_owns_process(identity.launcher_pid, os.getpid())
            or win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        latch = WindowsRuntimeStopLatch(expected_owner=binding.os_owner_id, name=identity.stop_name, create=False)
        try:
            latch.retain_parent(owner)
        except BaseException as error:
            latch.__exit__(type(error), error, error.__traceback__)
            raise
        transferred = True
        return latch
    except BaseException as error:
        primaries.append(error)
        raise
    finally:
        if not transferred:
            try:
                owner.close_now()
            except BaseException as failure:
                retained = AsyncResourceCleanupError(
                    (owner,), (failure,), retry_task_name="runtime-launcher-parent-close", close_attempts=1
                )
                if not primaries:
                    raise retained from failure
                primary = primaries[0]
                for previous in async_cleanup_failures(primary):
                    retained = previous.merged_with(retained)
                primary.__dict__["async_cleanup_error"] = retained
                if isinstance(primary.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                    primary.__dict__["cleanup_error"] = retained
