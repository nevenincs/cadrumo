"""Portable coalition enumeration and convergent termination through a synthetic kernel port."""

from __future__ import annotations

import ctypes
import errno
import math
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, override

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import macos_coalition as native
from ..macos_coalition import (
    _CoalitionInfo,
    decode_macos_resource_coalition,
    macos_coalition_members,
    terminate_macos_coalition,
)
from ..macos_process import MacosProcessIncarnation, MacosSignalDelivery

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_OWNED = 7001
_FOREIGN = 7002


def _incarnation(pid: int, version: int = 1) -> MacosProcessIncarnation:
    return MacosProcessIncarnation(pid=pid, version=version, unique_id=pid * 1000 + version)


class _Kernel:
    """Synthetic process table; SIGKILL removes only the exact signalled incarnation."""

    def __init__(self, processes: dict[int, tuple[int, MacosProcessIncarnation]]) -> None:
        self.processes = dict(processes)
        self.signals: list[MacosProcessIncarnation] = []
        self.on_kill: dict[int, Callable[[], None]] = {}
        self.dying: dict[MacosProcessIncarnation, int] = {}
        self.listings = 0

    def process_ids(self) -> tuple[int, ...]:
        self.listings += 1
        return tuple(sorted(self.processes))

    def resource_coalition(self, pid: int) -> int | None:
        entry = self.processes.get(pid)
        return entry[0] if entry is not None else None

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        entry = self.processes.get(pid)
        if entry is None:
            return None
        remaining = self.dying.get(entry[1])
        if remaining is not None:
            # A killed process stays readable for a few reads while it exits.
            if remaining <= 0:
                del self.processes[pid]
                del self.dying[entry[1]]
                return None
            self.dying[entry[1]] = remaining - 1
        return entry[1]

    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        assert signal_number == 9
        self.signals.append(incarnation)
        entry = self.processes.get(incarnation.pid)
        if entry is None or entry[1] != incarnation:
            return MacosSignalDelivery.GONE
        if incarnation in self.dying:
            return MacosSignalDelivery.DELIVERED
        self.dying[incarnation] = 0
        hook = self.on_kill.pop(incarnation.pid, None)
        if hook is not None:
            hook()
        return MacosSignalDelivery.DELIVERED


def _deadline(seconds: float = 2.0) -> float:
    return time.monotonic() + seconds


def test_fork_racing_the_kill_is_reached_by_a_later_pass() -> None:
    parent, child, foreign = _incarnation(10), _incarnation(11), _incarnation(12)
    kernel = _Kernel({10: (_OWNED, parent), 12: (_FOREIGN, foreign)})
    # The child is created inside the coalition while its parent is being killed.
    kernel.on_kill[10] = lambda: kernel.processes.__setitem__(11, (_OWNED, child))
    terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert kernel.signals == [parent, child]
    assert set(kernel.processes) == {12}


class _SlowExitKernel(_Kernel):
    @override
    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        first = incarnation not in self.dying
        delivered = super().signal(incarnation, signal_number)
        if first and delivered is MacosSignalDelivery.DELIVERED:
            self.dying[incarnation] = 3
        return delivered


def test_killed_member_still_exiting_keeps_termination_open() -> None:
    member = _incarnation(20)
    kernel = _SlowExitKernel({20: (_OWNED, member)})
    terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert kernel.processes == {}
    # Two quiet passes are counted only after the killed incarnation was gone.
    assert kernel.listings >= 4


def test_excluded_exact_incarnation_is_never_signalled() -> None:
    guardian, worker = _incarnation(30), _incarnation(31)
    kernel = _Kernel({30: (_OWNED, guardian), 31: (_OWNED, worker)})
    terminate_macos_coalition(_OWNED, deadline=_deadline(), exclude=guardian, port=kernel)
    assert kernel.signals == [worker]
    assert set(kernel.processes) == {30}


class _ReusingKernel(_Kernel):
    """The member exits and a foreign process takes its PID between two coalition reads."""

    def __init__(
        self, processes: dict[int, tuple[int, MacosProcessIncarnation]], reused: MacosProcessIncarnation
    ) -> None:
        super().__init__(processes)
        self.reused = reused
        self.reads = 0

    @override
    def resource_coalition(self, pid: int) -> int | None:
        self.reads += 1
        if pid == self.reused.pid and self.reads == 2:
            self.processes[pid] = (_FOREIGN, self.reused)
        return super().resource_coalition(pid)


def test_reused_pid_between_reads_is_not_attributed_to_the_coalition() -> None:
    reused = _incarnation(40, version=2)
    kernel = _ReusingKernel({40: (_OWNED, _incarnation(40))}, reused)
    assert macos_coalition_members(_OWNED, port=kernel) == ()
    terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert kernel.signals == []
    assert kernel.processes == {40: (_FOREIGN, reused)}


class _ExitingKernel(_Kernel):
    @override
    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        assert signal_number == 9
        self.signals.append(incarnation)
        self.processes.pop(incarnation.pid, None)
        return MacosSignalDelivery.GONE


def test_member_exiting_before_its_signal_is_gone_not_refused() -> None:
    member = _incarnation(50)
    kernel = _ExitingKernel({50: (_OWNED, member)})
    terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert kernel.signals == [member] and kernel.processes == {}


class _RefusingKernel(_Kernel):
    @override
    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def test_refused_signal_fails_closed() -> None:
    kernel = _RefusingKernel({60: (_OWNED, _incarnation(60))})
    with pytest.raises(RuntimeRefusalError) as caught:
        terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


class _UnreadableKernel(_Kernel):
    @override
    def resource_coalition(self, pid: int) -> int | None:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def test_unreadable_process_fails_closed_rather_than_being_skipped() -> None:
    kernel = _UnreadableKernel({70: (_OWNED, _incarnation(70))})
    with pytest.raises(RuntimeRefusalError) as caught:
        terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


class _UnkillableKernel(_Kernel):
    @override
    def signal(self, incarnation: MacosProcessIncarnation, signal_number: int) -> MacosSignalDelivery:
        assert signal_number == 9
        self.signals.append(incarnation)
        return MacosSignalDelivery.DELIVERED


def test_member_that_never_dies_exceeds_the_deadline() -> None:
    member = _incarnation(80)
    kernel = _UnkillableKernel({80: (_OWNED, member)})
    with pytest.raises(RuntimeRefusalError) as caught:
        terminate_macos_coalition(_OWNED, deadline=_deadline(0.05), port=kernel)
    assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert len(kernel.signals) >= 2


def test_empty_coalition_needs_two_quiet_passes() -> None:
    kernel = _Kernel({90: (_FOREIGN, _incarnation(90))})
    terminate_macos_coalition(_OWNED, deadline=_deadline(), port=kernel)
    assert kernel.listings == 2 and kernel.signals == []


@pytest.mark.parametrize(("coalition", "deadline"), [(0, 1.0), (-1, 1.0), (_OWNED, math.nan), (_OWNED, math.inf)])
def test_invalid_termination_request_refuses_before_native_access(coalition: int, deadline: float) -> None:
    kernel = _Kernel({})
    with pytest.raises(RuntimeRefusalError) as caught:
        terminate_macos_coalition(coalition, deadline=deadline, port=kernel)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert kernel.listings == 0


def _coalition_record(resource: int, jetsam: int = 99) -> bytes:
    value = _CoalitionInfo()
    value.coalition_ids[0], value.coalition_ids[1] = resource, jetsam
    return ctypes.string_at(ctypes.byref(value), ctypes.sizeof(value))


def test_coalition_record_uses_the_resource_word() -> None:
    assert ctypes.sizeof(_CoalitionInfo) == 40
    assert decode_macos_resource_coalition(_coalition_record(1056028)) == 1056028


@pytest.mark.parametrize("payload", [_coalition_record(0), _coalition_record(5)[:-1], b""])
def test_incomplete_or_null_coalition_record_refuses(payload: bytes) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        decode_macos_resource_coalition(payload)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


class _NativeFunction:
    argtypes: tuple[object, ...] = ()
    restype: object = None

    def __init__(self, call: Callable[..., int]) -> None:
        self._call = call

    def __call__(self, *arguments: Any) -> int:
        return self._call(*arguments)


@pytest.mark.parametrize(
    ("count", "error_number", "expected"),
    [(40, 0, 1056028), (0, errno.ESRCH, None), (0, errno.EPERM, RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)],
)
def test_native_coalition_read_distinguishes_gone_from_unreadable(
    monkeypatch: pytest.MonkeyPatch, count: int, error_number: int, expected: int | RuntimeRefusalCode | None
) -> None:
    from .. import macos_process

    record = _coalition_record(1056028)

    def query(pid: int, flavor: int, argument: int, buffer: ctypes.c_void_p, size: int) -> int:
        assert (pid, flavor, argument, size) == (123, 20, 0, 40)
        ctypes.memmove(buffer, record, len(record))
        ctypes.set_errno(error_number)
        return count

    monkeypatch.setattr(macos_process.sys, "platform", "darwin")
    monkeypatch.setattr(
        native.ctypes, "CDLL", lambda _name, *, use_errno: SimpleNamespace(proc_pidinfo=_NativeFunction(query))
    )
    if isinstance(expected, RuntimeRefusalCode):
        with pytest.raises(RuntimeRefusalError) as caught:
            native.read_macos_resource_coalition(123)
        assert caught.value.reason is expected
    else:
        assert native.read_macos_resource_coalition(123) == expected


def test_native_listing_grows_until_it_is_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    live = [0, 501, 77, 77, 1, 9000, 12, 13]
    capacities: list[int] = []

    def listing(buffer: ctypes.c_void_p | None, size: int) -> int:
        if buffer is None:
            return 3
        capacity = size // ctypes.sizeof(ctypes.c_int)
        capacities.append(capacity)
        written = live[:capacity]
        array = (ctypes.c_int * len(written))(*written)
        ctypes.memmove(buffer, array, ctypes.sizeof(array))
        return len(written)

    monkeypatch.setattr(native, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(
        native.ctypes, "CDLL", lambda _name, *, use_errno: SimpleNamespace(proc_listallpids=_NativeFunction(listing))
    )
    assert native.list_macos_process_ids() == (1, 12, 13, 77, 501, 9000)
    # A full buffer is never accepted as a complete listing.
    assert capacities == [6, 12]


def test_native_views_refuse_off_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(RuntimeRefusalError):
        native.list_macos_process_ids()
    with pytest.raises(RuntimeRefusalError):
        native.read_macos_resource_coalition(1)
