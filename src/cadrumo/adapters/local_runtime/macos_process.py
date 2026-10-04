"""Kernel process incarnation and retained exit observations on macOS."""

from __future__ import annotations

import ctypes
import errno
import math
import os
import struct
import sys
from dataclasses import dataclass
from enum import StrEnum

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.async_cleanup import AsyncResourceCleanupError

# Darwin libproc PROC_PIDUNIQIDENTIFIERINFO: the kernel's private record carrying
# the per-incarnation pidversion that audit tokens and exact signalling compare.
_PROC_PIDUNIQIDENTIFIERINFO = 17
_MAXIMUM_PID = 2_147_483_647
_MAXIMUM_NATIVE_ID = 0xFFFFFFFF


class _BsdProcessInfo(ctypes.Structure):
    _fields_ = (
        ("flags", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
        ("exit_status", ctypes.c_uint32),
        ("pid", ctypes.c_uint32),
        ("parent_pid", ctypes.c_uint32),
        ("uid", ctypes.c_uint32),
        ("gid", ctypes.c_uint32),
        ("real_uid", ctypes.c_uint32),
        ("real_gid", ctypes.c_uint32),
        ("saved_uid", ctypes.c_uint32),
        ("saved_gid", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
        ("command", ctypes.c_char * 16),
        ("name", ctypes.c_char * 32),
        ("file_count", ctypes.c_uint32),
        ("group_id", ctypes.c_uint32),
        ("job_count", ctypes.c_uint32),
        ("terminal", ctypes.c_uint32),
        ("terminal_group", ctypes.c_uint32),
        ("nice", ctypes.c_int32),
        ("started_seconds", ctypes.c_uint64),
        ("started_microseconds", ctypes.c_uint64),
    )


class _UniqueIdentifierInfo(ctypes.Structure):
    _fields_ = (
        ("executable_uuid", ctypes.c_uint8 * 16),
        ("unique_id", ctypes.c_uint64),
        ("parent_unique_id", ctypes.c_uint64),
        ("version", ctypes.c_int32),
        ("original_parent_version", ctypes.c_int32),
        ("reserved_first", ctypes.c_uint64),
        ("reserved_second", ctypes.c_uint64),
    )


class _KernelEvent(ctypes.Structure):
    _fields_ = (
        ("ident", ctypes.c_size_t),
        ("filter", ctypes.c_int16),
        ("flags", ctypes.c_uint16),
        ("events", ctypes.c_uint32),
        ("data", ctypes.c_ssize_t),
        ("user_data", ctypes.c_void_p),
    )


class _Timespec(ctypes.Structure):
    _fields_ = (("seconds", ctypes.c_long), ("nanoseconds", ctypes.c_long))


@dataclass(frozen=True, slots=True)
class MacosProcessObservation:
    """Nonsecret kernel identity; a PID alone is never a retained capability."""

    pid: int
    os_owner_id: str
    parent_pid: int
    process_group_id: int
    started_seconds: int
    started_microseconds: int


def decode_macos_process_info(payload: bytes, *, pid: int, expected_owner: str) -> MacosProcessObservation:
    """Validate a complete native BSD process record without reading account names.

    Args:
        payload: Exact native proc_bsdinfo record.
        pid: Expected kernel-derived process ID.
        expected_owner: Independently verified native process UID.
    """
    if len(payload) != ctypes.sizeof(_BsdProcessInfo) or type(pid) is not int or not 0 < pid <= 2_147_483_647:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    value = _BsdProcessInfo.from_buffer_copy(payload)
    _require_bsd_process_identity(value, pid, expected_owner)
    return MacosProcessObservation(
        pid=pid,
        os_owner_id=expected_owner,
        parent_pid=int(value.parent_pid),
        process_group_id=int(value.group_id),
        started_seconds=int(value.started_seconds),
        started_microseconds=int(value.started_microseconds),
    )


def read_macos_process(pid: int, *, expected_owner: str) -> MacosProcessObservation:
    """Read the exact owner's live process and kernel creation timestamp.

    Args:
        pid: Kernel-derived process ID, bounded before native integer conversion.
        expected_owner: Native UID supplied by the owning transport or launch scope.
    """
    if sys.platform != "darwin" or type(pid) is not int or not 0 < pid <= 2_147_483_647:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    try:
        native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = native.proc_pidinfo
        query.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int)
        query.restype = ctypes.c_int
        value = _BsdProcessInfo()
        ctypes.set_errno(0)
        count = query(pid, 3, 0, ctypes.byref(value), ctypes.sizeof(value))
        native_errno = ctypes.get_errno()
        if count == 0 and native_errno == errno.EPERM:
            # launchd can publish a PID before its BSD identity is readable.
            # No identity is released; an owning launch scope may retry its
            # exact candidate within its already declared readiness deadline.
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if count != ctypes.sizeof(value):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return decode_macos_process_info(
            ctypes.string_at(ctypes.byref(value), ctypes.sizeof(value)),
            pid=pid,
            expected_owner=expected_owner,
        )
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None


@dataclass(frozen=True, slots=True)
class MacosProcessIncarnation:
    """One exact process lifetime: a PID is reusable, its kernel version is not.

    Darwin assigns a fresh pidversion at creation and again at each exec, so an
    incarnation names one program image of one process, never a later reuse.
    """

    pid: int
    version: int
    unique_id: int


class MacosSignalDelivery(StrEnum):
    """Outcome of exact-incarnation signalling; refusal is raised, never returned."""

    DELIVERED = "delivered"
    GONE = "gone"


def decode_macos_incarnation(payload: bytes, *, pid: int) -> MacosProcessIncarnation:
    """Validate a complete native unique-identifier record for one expected PID.

    Args:
        payload: Exact native proc_uniqidentifierinfo record.
        pid: Kernel PID the record was requested for.
    """
    if len(payload) != ctypes.sizeof(_UniqueIdentifierInfo) or type(pid) is not int or not 0 < pid <= _MAXIMUM_PID:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    value = _UniqueIdentifierInfo.from_buffer_copy(payload)
    if not 0 < value.version <= _MAXIMUM_PID or value.unique_id <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return MacosProcessIncarnation(pid=pid, version=int(value.version), unique_id=int(value.unique_id))


def read_macos_incarnation(pid: int) -> MacosProcessIncarnation | None:
    """Read the live incarnation of a PID; None means no live process holds it.

    Exited and zombie processes are absent. Any other native failure refuses,
    so an unreadable process is never mistaken for a gone one.

    Args:
        pid: Kernel PID, bounded before native integer conversion.
    """
    if sys.platform != "darwin" or type(pid) is not int or not 0 < pid <= _MAXIMUM_PID:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = native.proc_pidinfo
        query.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int)
        query.restype = ctypes.c_int
        value = _UniqueIdentifierInfo()
        ctypes.set_errno(0)
        count = query(pid, _PROC_PIDUNIQIDENTIFIERINFO, 0, ctypes.byref(value), ctypes.sizeof(value))
        if count <= 0 and ctypes.get_errno() == errno.ESRCH:
            return None
        if count != ctypes.sizeof(value):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return decode_macos_incarnation(ctypes.string_at(ctypes.byref(value), ctypes.sizeof(value)), pid=pid)
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None


def macos_audit_token(incarnation: MacosProcessIncarnation, *, user_id: int, group_id: int) -> bytes:
    """Encode the eight-word audit token that names one exact incarnation.

    The kernel resolves the token by PID and pidversion, so a stale token can
    never reach a later process that reused the PID.

    Args:
        incarnation: Exact target process lifetime.
        user_id: Native owner UID placed in the audit and credential words.
        group_id: Native owner GID placed in the credential words.
    """
    if (
        not 0 < incarnation.pid <= _MAXIMUM_PID
        or not 0 < incarnation.version <= _MAXIMUM_PID
        or not 0 <= user_id <= _MAXIMUM_NATIVE_ID
        or not 0 <= group_id <= _MAXIMUM_NATIVE_ID
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    # audit_token_t words: auid, euid, egid, ruid, rgid, pid, asid, pidversion.
    return struct.pack("=8I", user_id, user_id, group_id, user_id, group_id, incarnation.pid, 0, incarnation.version)


def signal_macos_incarnation(incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
    """Deliver a signal only to the exact incarnation, through its kernel audit token.

    Args:
        incarnation: Exact target process lifetime.
        signal_number: Native BSD signal number to deliver.
    """
    if type(signal_number) is not int or not 0 < signal_number < 32:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    if sys.platform == "darwin":
        token = (ctypes.c_uint32 * 8).from_buffer_copy(
            macos_audit_token(incarnation, user_id=os.getuid(), group_id=os.getgid())
        )
        try:
            native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            deliver = native.proc_signal_with_audittoken
            deliver.argtypes = (ctypes.c_void_p, ctypes.c_int)
            deliver.restype = ctypes.c_int
            ctypes.set_errno(0)
            result = deliver(ctypes.byref(token), signal_number)
            # libproc returns the native errno directly; tolerate a -1/errno form too.
            return macos_signal_delivery(ctypes.get_errno() if result == -1 else result)
        except (AttributeError, OSError):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def macos_signal_delivery(result: int) -> MacosSignalDelivery:
    """Classify a native exact-token signal result; any refusal raises.

    Args:
        result: Native errno-style result of proc_signal_with_audittoken.
    """
    if result == 0:
        return MacosSignalDelivery.DELIVERED
    if result == errno.ESRCH:
        return MacosSignalDelivery.GONE
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


class MacosProcessWatch:
    """Retain a noninherited kqueue exit filter for one verified incarnation.

    This watches one process. It does not claim descendant containment or make
    a process group safe against independently regrouped children.
    """

    observation: MacosProcessObservation

    def __init__(self, observation: MacosProcessObservation) -> None:
        """Register exit observation between two matching kernel identity reads.

        Args:
            observation: Exact kernel identity retained by the resource owner.
        """
        if sys.platform != "darwin":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self.observation = observation
        self._descriptor = -1
        self._exited = False
        try:
            native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            create = native.kqueue
            create.argtypes = ()
            create.restype = ctypes.c_int
            descriptor = create()
            if descriptor < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._descriptor = descriptor
            os.set_inheritable(descriptor, False)
            if read_macos_process(observation.pid, expected_owner=observation.os_owner_id) != observation:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            change = _KernelEvent(observation.pid, -5, 0x0001 | 0x0004 | 0x0020, 0x80000000, 0, None)
            self._event(change=change)
            if (
                read_macos_process(observation.pid, expected_owner=observation.os_owner_id) != observation
                or self.exited
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        except BaseException as error:
            primary = _watch_failure(error)
            self._close_failed_watch(primary)
            if primary is error:
                raise
            raise primary from error

    def _close_failed_watch(self, primary: BaseException) -> None:
        """Retire the descriptor once and preserve all prior cleanup ownership."""
        try:
            self.close()
        except BaseException as cleanup:
            _retain_watch_close_failure(primary, cleanup)

    def _event(self, *, change: _KernelEvent | None = None, timeout: float = 0) -> bool:
        if self._descriptor < 0 or not math.isfinite(timeout) or timeout < 0 or timeout > 60:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        try:
            native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            control = native.kevent
            control.argtypes = (
                ctypes.c_int,
                ctypes.POINTER(_KernelEvent),
                ctypes.c_int,
                ctypes.POINTER(_KernelEvent),
                ctypes.c_int,
                ctypes.POINTER(_Timespec),
            )
            control.restype = ctypes.c_int
            event = _KernelEvent()
            seconds = int(timeout)
            duration = _Timespec(seconds, int((timeout - seconds) * 1_000_000_000))
            count = control(
                self._descriptor,
                ctypes.byref(change) if change is not None else None,
                int(change is not None),
                ctypes.byref(event),
                1,
                ctypes.byref(duration),
            )
            _require_kernel_event(count, event, self.observation.pid)
            if count and event.events & 0x80000000:
                self._exited = True
            return self._exited
        except (AttributeError, OSError):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    @property
    def exited(self) -> bool:
        """Latch exit permanently, including after a PID is reused."""
        return self._exited or self._event()

    def wait(self, *, timeout: float) -> bool:
        """Wait within the caller's finite budget for this exact process exit.

        Args:
            timeout: Finite wait budget in seconds, at most sixty.
        """
        return self._exited or self._event(timeout=timeout)

    def close(self) -> None:
        """Retire this capability before attempting its native descriptor close.

        Darwin may consume the FD slot even when close reports failure. Never
        retry that number: it could already refer to an unrelated resource.
        Retirement alone does not certify successful physical native release.
        """
        if self._descriptor >= 0:
            descriptor, self._descriptor = self._descriptor, -1
            os.close(descriptor)


def _require_bsd_process_identity(value: _BsdProcessInfo, pid: int, expected_owner: str) -> None:
    """Admit only the expected live native identity and complete creation timestamp."""
    if (
        value.pid != pid
        or str(value.uid) != expected_owner
        or value.real_uid != value.uid
        or value.saved_uid != value.uid
        or value.status == 5
        or value.flags & 4
        or value.started_seconds <= 0
        or not 0 <= value.started_microseconds < 1_000_000
        or value.group_id <= 0
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)


def _watch_failure(error: BaseException) -> BaseException:
    """Translate native watch failures while retaining attached cleanup owners."""
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) if isinstance(error, (AttributeError, OSError)) else error
    )
    if primary is not error:
        for name in ("async_cleanup_error", "cleanup_error"):
            previous = error.__dict__.get(name)
            if isinstance(previous, BaseException):
                primary.__dict__[name] = previous
    return primary


def _retain_watch_close_failure(primary: BaseException, cleanup: BaseException) -> None:
    """Preserve a consumed descriptor as diagnostic and retain earlier retry owners."""
    previous = primary.__dict__.get("cleanup_error")
    if isinstance(previous, AsyncResourceCleanupError):
        # The FD slot may have been consumed despite native failure.
        # Preserve earlier retry owners; this failure is diagnostic,
        # never another authority to close a reusable descriptor.
        diagnostic = AsyncResourceCleanupError(
            (), (cleanup,), retry_task_name="macos-process-watch-cleanup", close_attempts=1
        )
        retained = previous.merged_with(diagnostic)
        retained.__cause__ = cleanup
        primary.__dict__["cleanup_error"] = retained
        if primary.__dict__.get("async_cleanup_error") is previous:
            primary.__dict__["async_cleanup_error"] = retained
    elif isinstance(previous, BaseException) and previous is not cleanup:
        primary.__dict__["cleanup_error"] = BaseExceptionGroup(
            "macOS process watch cleanup failed", (previous, cleanup)
        )
    elif cleanup is not primary:
        primary.__dict__["cleanup_error"] = cleanup
    primary.add_note("Process watch native close also failed; its descriptor capability was retired")


def _require_kernel_event(count: int, event: _KernelEvent, pid: int) -> None:
    """Refuse native errors or an event for another process before latching exit."""
    if count < 0 or (count and event.flags & 0x4000):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    if count and (event.ident != pid or event.filter != -5):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
