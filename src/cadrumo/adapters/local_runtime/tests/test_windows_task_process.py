"""Synthetic native-port tests for Task Scheduler process ancestry."""

from __future__ import annotations

import ctypes
from collections.abc import Callable, Mapping

import pytest

from .. import windows_task_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SNAPSHOT_HANDLE = 91


class _NativeFunction:
    def __init__(self, callback: Callable[..., object]) -> None:
        self.callback = callback
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *arguments: object) -> object:
        return self.callback(*arguments)


class _FrozenToolhelpSnapshot:
    """A fixed Toolhelp table that writes the production PROCESSENTRY32 layout."""

    def __init__(self, parents: dict[int, int]) -> None:
        self.parents = tuple(parents.items())
        self.cursor = -1
        self.closed_handles: list[int] = []
        self.CreateToolhelp32Snapshot = _NativeFunction(self._create_snapshot)
        self.Process32FirstW = _NativeFunction(self._first)
        self.Process32NextW = _NativeFunction(self._next)
        self.CloseHandle = _NativeFunction(self._close)

    def _create_snapshot(self, flags: object, process_id: object) -> int:
        assert flags == 0x00000002
        assert process_id == 0
        self.cursor = -1
        return _SNAPSHOT_HANDLE

    def _write_current(
        self,
        snapshot: object,
        entry_pointer: ctypes._Pointer[windows_task_process._ProcessEntry],
    ) -> bool:
        assert snapshot == _SNAPSHOT_HANDLE
        if not 0 <= self.cursor < len(self.parents):
            return False
        process_id, parent_id = self.parents[self.cursor]
        entry = entry_pointer.contents
        assert entry.dwSize == ctypes.sizeof(windows_task_process._ProcessEntry)
        entry.th32ProcessID = process_id
        entry.th32ParentProcessID = parent_id
        return True

    def _first(
        self,
        snapshot: object,
        entry_pointer: ctypes._Pointer[windows_task_process._ProcessEntry],
    ) -> bool:
        self.cursor = 0
        return self._write_current(snapshot, entry_pointer)

    def _next(
        self,
        snapshot: object,
        entry_pointer: ctypes._Pointer[windows_task_process._ProcessEntry],
    ) -> bool:
        self.cursor += 1
        return self._write_current(snapshot, entry_pointer)

    def _close(self, handle: object) -> bool:
        assert isinstance(handle, int)
        self.closed_handles.append(handle)
        return True


def _install_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    parents: dict[int, int],
    births: Mapping[int, int | None],
) -> tuple[_FrozenToolhelpSnapshot, list[int]]:
    snapshot = _FrozenToolhelpSnapshot(parents)
    birth_calls: list[int] = []

    def load_library(name: str, *, use_last_error: bool) -> object:
        assert name == "kernel32"
        assert use_last_error is True
        return snapshot

    def creation_time(_kernel: ctypes.CDLL, process_id: int) -> int | None:
        birth_calls.append(process_id)
        return births.get(process_id)

    def entry_pointer(
        value: windows_task_process._ProcessEntry,
    ) -> ctypes._Pointer[windows_task_process._ProcessEntry]:
        return ctypes.pointer(value)

    monkeypatch.setattr(windows_task_process.ctypes, "WinDLL", load_library, raising=False)
    monkeypatch.setattr(windows_task_process.ctypes, "byref", entry_pointer)
    monkeypatch.setattr(windows_task_process, "_creation_time", creation_time)
    return snapshot, birth_calls


def _five_entry_chain() -> tuple[dict[int, int], dict[int, int]]:
    """The server PID followed by three launch intermediates and task engine."""
    parents = {205: 204, 204: 203, 203: 202, 202: 201, 201: 4}
    births = {201: 100, 202: 200, 203: 300, 204: 400, 205: 500, 4: 1}
    return parents, births


def test_accepts_five_entry_engine_to_peer_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    parents, births = _five_entry_chain()
    snapshot, _birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=201, process_pid=205) is True
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]


def test_unrelated_engine_pid_is_not_accepted_from_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    parents, births = _five_entry_chain()
    parents[999] = 4
    births[999] = 50
    snapshot, _birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=999, process_pid=205) is False
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]


def test_reused_parent_with_later_birth_is_refused_and_snapshot_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    parents, births = _five_entry_chain()
    births[204] = 600
    snapshot, _birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=201, process_pid=205) is False
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]


def test_missing_required_native_birth_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    parents, births = _five_entry_chain()
    births.pop(204)
    snapshot, _birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=201, process_pid=205) is False
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]


def test_ancestry_beyond_eight_entries_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    parents = {pid: pid - 1 for pid in range(109, 99, -1)}
    births = {pid: (pid - 100) * 100 for pid in range(100, 110)}
    snapshot, _birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=100, process_pid=109) is False
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]


def test_cycle_is_bounded_and_snapshot_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    parents = {301: 302, 302: 301}
    births = {301: 100, 302: 100}
    snapshot, birth_calls = _install_snapshot(monkeypatch, parents, births)

    assert windows_task_process.task_engine_owns_process(engine_pid=999, process_pid=301) is False
    assert len(birth_calls) == 9
    assert snapshot.closed_handles == [_SNAPSHOT_HANDLE]
