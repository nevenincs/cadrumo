"""Darwin resource-coalition membership and convergent exact-incarnation termination.

launchd places each bootstrapped job in a fresh resource coalition. Members keep
it through setsid, setpgid, double-fork orphaning and exec, so the coalition is
the owned descendant scope that process groups alone cannot provide.
"""

from __future__ import annotations

import ctypes
import errno
import math
import sys
import time
from typing import Protocol

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .macos_process import (
    MacosProcessIncarnation,
    MacosSignalDelivery,
    read_macos_incarnation,
    signal_macos_incarnation,
)

# Darwin libproc PROC_PIDCOALITIONINFO; word 0 is the resource coalition.
_PROC_PIDCOALITIONINFO = 20
_MAXIMUM_PID = 2_147_483_647
_MAXIMUM_LISTED_PROCESSES = 1 << 20
_SIGKILL = 9
_QUIET_PASSES = 2
_PASS_INTERVAL_SECONDS = 0.002


class _CoalitionInfo(ctypes.Structure):
    _fields_ = (("coalition_ids", ctypes.c_uint64 * 2), ("reserved", ctypes.c_uint64 * 3))


def decode_macos_resource_coalition(payload: bytes) -> int:
    """Validate a complete native coalition record and return its resource coalition.

    Args:
        payload: Exact native proc_pidcoalitioninfo record.
    """
    if len(payload) != ctypes.sizeof(_CoalitionInfo):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    value = _CoalitionInfo.from_buffer_copy(payload)
    coalition = int(value.coalition_ids[0])
    if coalition <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return coalition


def read_macos_resource_coalition(pid: int) -> int | None:
    """Read a live process's resource coalition; None means no live process holds the PID.

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
        value = _CoalitionInfo()
        ctypes.set_errno(0)
        count = query(pid, _PROC_PIDCOALITIONINFO, 0, ctypes.byref(value), ctypes.sizeof(value))
        if count <= 0 and ctypes.get_errno() == errno.ESRCH:
            return None
        if count != ctypes.sizeof(value):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return decode_macos_resource_coalition(ctypes.string_at(ctypes.byref(value), ctypes.sizeof(value)))
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None


def list_macos_process_ids() -> tuple[int, ...]:
    """Snapshot every live PID, growing the buffer until the listing is not truncated."""
    if sys.platform != "darwin":
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        listing = native.proc_listallpids
        listing.argtypes = (ctypes.c_void_p, ctypes.c_int)
        listing.restype = ctypes.c_int
        # A null buffer reports the kernel's current count estimate, in PIDs.
        estimate = listing(None, 0)
        if estimate <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        capacity = estimate * 2
        while capacity <= _MAXIMUM_LISTED_PROCESSES:
            buffer = (ctypes.c_int * capacity)()
            count = listing(ctypes.byref(buffer), ctypes.sizeof(buffer))
            if count < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            if count < capacity:
                return tuple(sorted({int(pid) for pid in buffer[:count] if pid > 0}))
            # A full buffer may be a truncated listing; never treat it as complete.
            capacity *= 2
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


class MacosCoalitionPort(Protocol):
    """Native process facts and exact signalling consumed by coalition termination."""

    def process_ids(self) -> tuple[int, ...]:
        """Snapshot every live PID."""
        ...

    def resource_coalition(self, pid: int) -> int | None:
        """Read one live PID's resource coalition; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        """Read one live PID's exact incarnation; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        """Signal one exact incarnation; refusal raises.

        Args:
            incarnation: Exact target process lifetime.
            signal_number: Native BSD signal number.
        """
        ...


class NativeMacosCoalitionPort:
    """The Darwin kernel's libproc views behind the coalition termination contract."""

    def process_ids(self) -> tuple[int, ...]:
        """Snapshot every live PID."""
        return list_macos_process_ids()

    def resource_coalition(self, pid: int) -> int | None:
        """Read one live PID's resource coalition.

        Args:
            pid: Kernel PID.
        """
        return read_macos_resource_coalition(pid)

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        """Read one live PID's exact incarnation.

        Args:
            pid: Kernel PID.
        """
        return read_macos_incarnation(pid)

    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        """Signal one exact incarnation through its audit token.

        Args:
            incarnation: Exact target process lifetime.
            signal_number: Native BSD signal number.
        """
        return signal_macos_incarnation(incarnation, signal_number)


def macos_coalition_members(coalition: int, *, port: MacosCoalitionPort) -> tuple[MacosProcessIncarnation, ...]:
    """Bind every current member of one resource coalition to its exact incarnation.

    The coalition is read again after the incarnation, so a PID reused between
    the reads is never attributed to the coalition.

    Args:
        coalition: Resource coalition ID.
        port: Native process facts.
    """
    if type(coalition) is not int or coalition <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    members: list[MacosProcessIncarnation] = []
    for pid in port.process_ids():
        if port.resource_coalition(pid) != coalition:
            continue
        incarnation = port.incarnation(pid)
        if incarnation is None or port.resource_coalition(pid) != coalition:
            continue
        members.append(incarnation)
    return tuple(members)


def terminate_macos_coalition(
    coalition: int,
    *,
    deadline: float,
    exclude: MacosProcessIncarnation | None = None,
    port: MacosCoalitionPort | None = None,
) -> None:
    """SIGKILL every coalition member until the coalition is proven empty, within a deadline.

    Members may fork while they are being killed. A pass counts as quiet only
    when it finds no member and every incarnation signalled earlier had already
    died before the pass started its listing; two consecutive quiet passes end
    termination. An excluded exact incarnation (the calling guardian) is never
    signalled and does not count as a remaining member.

    Args:
        coalition: Resource coalition ID to empty.
        deadline: Monotonic deadline; exceeding it raises DEADLINE_EXCEEDED.
        exclude: Exact incarnation that must survive, if any.
        port: Native process facts; defaults to the Darwin kernel.
    """
    if type(coalition) is not int or coalition <= 0 or not math.isfinite(deadline):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    native = port if port is not None else NativeMacosCoalitionPort()
    signalled: set[MacosProcessIncarnation] = set()
    quiet = 0
    while True:
        signalled = {incarnation for incarnation in signalled if native.incarnation(incarnation.pid) == incarnation}
        members = tuple(member for member in macos_coalition_members(coalition, port=native) if member != exclude)
        for member in members:
            if native.signal(member, _SIGKILL) is MacosSignalDelivery.DELIVERED:
                signalled.add(member)
        quiet = quiet + 1 if not members and not signalled else 0
        if quiet >= _QUIET_PASSES:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        time.sleep(min(_PASS_INTERVAL_SECONDS, remaining))


__all__ = [
    "MacosCoalitionPort",
    "NativeMacosCoalitionPort",
    "decode_macos_resource_coalition",
    "list_macos_process_ids",
    "macos_coalition_members",
    "read_macos_resource_coalition",
    "terminate_macos_coalition",
]
