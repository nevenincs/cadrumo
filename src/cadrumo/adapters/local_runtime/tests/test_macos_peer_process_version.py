"""Kernel version corroboration follows the final socket and BSD identity reads."""

from __future__ import annotations

import ctypes
import errno
import socket
import struct
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import macos_login
from ..macos_process import MacosProcessObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PAYLOAD = struct.pack("=8I", 501, 501, 20, 501, 20, 123, 100022, 7)


class _KernelPeer:
    def fileno(self) -> int:
        return 42

    def getsockopt(self, level: int, option: int, size: int) -> bytes:
        assert level == 0
        if option == 6:
            assert size == 32
            return _PAYLOAD
        assert option == 2 and size == 4
        return struct.pack("=i", 123)


class _VersionQuery:
    argtypes: tuple[object, ...] = ()
    restype: object = None

    def __init__(self, *, result: int, error: int) -> None:
        self.result = result
        self.error = error
        self.tokens: list[tuple[int, ...]] = []

    def __call__(self, token: ctypes.c_void_p, buffer: ctypes.c_void_p, size: int) -> int:
        assert size == 4096
        words = ctypes.cast(token, ctypes.POINTER(ctypes.c_uint32 * 8)).contents
        self.tokens.append(tuple(words))
        ctypes.memmove(buffer, b"/bin/peer\0", 10)
        ctypes.set_errno(self.error)
        return self.result


def _install(monkeypatch: pytest.MonkeyPatch, *, query: _VersionQuery | None) -> None:
    def observe(pid: int, *, expected_owner: str) -> MacosProcessObservation:
        assert pid == 123 and expected_owner == "501"
        return MacosProcessObservation(pid, expected_owner, 1, pid, 1000, 1)

    def load(name: str, *, use_errno: bool) -> SimpleNamespace:
        assert name == "/usr/lib/libproc.dylib" and use_errno
        return SimpleNamespace() if query is None else SimpleNamespace(proc_pidpath_audittoken=query)

    monkeypatch.setattr(macos_login, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(macos_login, "ctypes", SimpleNamespace(**{**vars(ctypes), "CDLL": load}))
    monkeypatch.setattr(macos_login, "read_macos_process", observe)


def test_current_kernel_process_version_releases_only_the_audit_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    query = _VersionQuery(result=9, error=0)
    _install(monkeypatch, query=query)
    observed = macos_login.macos_peer_audit_token(cast(socket.socket, _KernelPeer()), expected_owner="501")
    assert observed.process_id == 123 and observed.process_version == 7
    assert query.tokens == [struct.unpack("=8I", _PAYLOAD)]


@pytest.mark.parametrize(
    "result,error,reason",
    [
        (0, errno.ESRCH, RuntimeRefusalCode.PEER_UNTRUSTED),
        (0, errno.EPERM, RuntimeRefusalCode.UNAVAILABLE),
        (0, errno.EACCES, RuntimeRefusalCode.UNAVAILABLE),
        (-1, 0, RuntimeRefusalCode.PEER_UNTRUSTED),
        (4096, 0, RuntimeRefusalCode.PEER_UNTRUSTED),
        (5, 0, RuntimeRefusalCode.PEER_UNTRUSTED),
    ],
)
def test_unchanged_pid_and_birth_cannot_substitute_for_current_kernel_version(
    monkeypatch: pytest.MonkeyPatch, result: int, error: int, reason: RuntimeRefusalCode
) -> None:
    query = _VersionQuery(result=result, error=error)
    _install(monkeypatch, query=query)
    with pytest.raises(RuntimeRefusalError) as caught:
        macos_login.macos_peer_audit_token(cast(socket.socket, _KernelPeer()), expected_owner="501")
    assert caught.value.reason is reason


def test_missing_version_validation_api_refuses_without_a_pid_only_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, query=None)
    with pytest.raises(RuntimeRefusalError) as caught:
        macos_login.macos_peer_audit_token(cast(socket.socket, _KernelPeer()), expected_owner="501")
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
