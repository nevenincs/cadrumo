"""Portable Darwin incarnation records and exact audit-token signalling through native doubles."""

from __future__ import annotations

import ctypes
import errno
import struct
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import macos_process as native
from ..macos_process import (
    MacosProcessIncarnation,
    MacosSignalDelivery,
    _UniqueIdentifierInfo,
    decode_macos_incarnation,
    macos_audit_token,
    macos_signal_delivery,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _record(*, version: int = 41, unique_id: int = 9_000_001) -> bytes:
    value = _UniqueIdentifierInfo()
    value.unique_id, value.parent_unique_id = unique_id, 9_000_000
    value.version, value.original_parent_version = version, 7
    return ctypes.string_at(ctypes.byref(value), ctypes.sizeof(value))


def test_incarnation_record_carries_pid_version_and_unique_identity() -> None:
    assert ctypes.sizeof(_UniqueIdentifierInfo) == 56
    assert decode_macos_incarnation(_record(), pid=123) == MacosProcessIncarnation(
        pid=123, version=41, unique_id=9_000_001
    )
    assert decode_macos_incarnation(_record(version=42), pid=123) != decode_macos_incarnation(_record(), pid=123)


@pytest.mark.parametrize(
    ("payload", "pid"),
    [
        (_record(version=0), 123),
        (_record(version=-1), 123),
        (_record(unique_id=0), 123),
        (_record()[:-1], 123),
        (_record(), 0),
        (_record(), 2_147_483_648),
    ],
)
def test_incomplete_or_null_incarnation_refuses(payload: bytes, pid: int) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        decode_macos_incarnation(payload, pid=pid)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


def test_audit_token_names_the_exact_pid_version_in_kernel_word_order() -> None:
    incarnation = MacosProcessIncarnation(pid=94587, version=1234, unique_id=1)
    token = macos_audit_token(incarnation, user_id=501, group_id=20)
    assert struct.unpack("=8I", token) == (501, 501, 20, 501, 20, 94587, 0, 1234)


@pytest.mark.parametrize(
    ("incarnation", "user_id", "group_id"),
    [
        (MacosProcessIncarnation(pid=0, version=1, unique_id=1), 501, 20),
        (MacosProcessIncarnation(pid=1, version=0, unique_id=1), 501, 20),
        (MacosProcessIncarnation(pid=1, version=1, unique_id=1), -1, 20),
        (MacosProcessIncarnation(pid=1, version=1, unique_id=1), 501, 0x1_0000_0000),
    ],
)
def test_audit_token_refuses_values_outside_its_native_words(
    incarnation: MacosProcessIncarnation, user_id: int, group_id: int
) -> None:
    with pytest.raises(RuntimeRefusalError):
        macos_audit_token(incarnation, user_id=user_id, group_id=group_id)


def test_signal_result_distinguishes_delivery_absence_and_refusal() -> None:
    assert macos_signal_delivery(0) is MacosSignalDelivery.DELIVERED
    assert macos_signal_delivery(errno.ESRCH) is MacosSignalDelivery.GONE
    for refused in (errno.EPERM, errno.EINVAL, -1):
        with pytest.raises(RuntimeRefusalError) as caught:
            macos_signal_delivery(refused)
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
    [
        (56, 0, MacosProcessIncarnation(pid=123, version=41, unique_id=9_000_001)),
        (0, errno.ESRCH, None),
        (0, errno.EPERM, RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE),
        (55, 0, RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE),
    ],
)
def test_native_incarnation_read_distinguishes_gone_from_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    error_number: int,
    expected: MacosProcessIncarnation | RuntimeRefusalCode | None,
) -> None:
    record = _record()

    def query(pid: int, flavor: int, argument: int, buffer: ctypes.c_void_p, size: int) -> int:
        assert (pid, flavor, argument, size) == (123, 17, 0, 56)
        ctypes.memmove(buffer, record, len(record))
        ctypes.set_errno(error_number)
        return count

    monkeypatch.setattr(native, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(
        native.ctypes, "CDLL", lambda _name, *, use_errno: SimpleNamespace(proc_pidinfo=_NativeFunction(query))
    )
    if isinstance(expected, RuntimeRefusalCode):
        with pytest.raises(RuntimeRefusalError) as caught:
            native.read_macos_incarnation(123)
        assert caught.value.reason is expected
    else:
        assert native.read_macos_incarnation(123) == expected


@pytest.mark.parametrize(
    ("result", "error_number", "expected"),
    [
        (0, 0, MacosSignalDelivery.DELIVERED),
        (errno.ESRCH, 0, MacosSignalDelivery.GONE),
        (-1, errno.ESRCH, MacosSignalDelivery.GONE),
        (errno.EPERM, 0, RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE),
    ],
)
def test_native_signal_passes_the_exact_incarnation_token(
    monkeypatch: pytest.MonkeyPatch,
    result: int,
    error_number: int,
    expected: MacosSignalDelivery | RuntimeRefusalCode,
) -> None:
    incarnation = MacosProcessIncarnation(pid=94587, version=1234, unique_id=1)
    delivered: list[tuple[bytes, int]] = []

    def deliver(token: Any, signal_number: int) -> int:
        delivered.append((ctypes.string_at(token, 32), signal_number))
        ctypes.set_errno(error_number)
        return result

    monkeypatch.setattr(native, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(native, "os", SimpleNamespace(getuid=lambda: 501, getgid=lambda: 20))
    monkeypatch.setattr(
        native.ctypes,
        "CDLL",
        lambda _name, *, use_errno: SimpleNamespace(proc_signal_with_audittoken=_NativeFunction(deliver)),
    )
    if isinstance(expected, RuntimeRefusalCode):
        with pytest.raises(RuntimeRefusalError) as caught:
            native.signal_macos_incarnation(incarnation, 9)
        assert caught.value.reason is expected
    else:
        assert native.signal_macos_incarnation(incarnation, 9) is expected
    assert delivered == [(macos_audit_token(incarnation, user_id=501, group_id=20), 9)]


@pytest.mark.parametrize("signal_number", [0, 32, -9])
def test_signal_number_outside_bsd_range_refuses_before_native_access(signal_number: int) -> None:
    with pytest.raises(RuntimeRefusalError):
        native.signal_macos_incarnation(MacosProcessIncarnation(pid=1, version=1, unique_id=1), signal_number)


def test_native_incarnation_views_refuse_off_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "sys", SimpleNamespace(platform="win32"))
    with pytest.raises(RuntimeRefusalError):
        native.read_macos_incarnation(1)
    with pytest.raises(RuntimeRefusalError):
        native.signal_macos_incarnation(MacosProcessIncarnation(pid=1, version=1, unique_id=1), 9)
