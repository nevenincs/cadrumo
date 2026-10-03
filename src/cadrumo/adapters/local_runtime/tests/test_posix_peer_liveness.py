"""Pinned POSIX peers prove liveness through their platform's exact kernel identity."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError

from .. import macos_login
from .. import posix_channel as posix
from ..macos_login import MacosPeerAuditToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _KernelSocket:
    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        return -1 if self.closed else 42

    def close(self) -> None:
        self.closed = True


def _token(pid: int) -> MacosPeerAuditToken:
    return MacosPeerAuditToken(501, 501, 20, 501, 20, pid, 100009, 77)


@pytest.fixture
def channel(monkeypatch: pytest.MonkeyPatch) -> Iterator[posix.PosixRuntimeChannel]:
    monkeypatch.setattr(posix, "_peer", lambda _socket: RuntimePeer(os_owner_id="501", process_id=123))
    connected = posix.PosixRuntimeChannel(cast(socket.socket, _KernelSocket()))
    try:
        yield connected
    finally:
        connected.close()


def test_darwin_liveness_rereads_the_exact_peer_audit_token(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixRuntimeChannel
) -> None:
    reads: list[str] = []

    def audit(_socket: object, *, expected_owner: str) -> MacosPeerAuditToken:
        reads.append(expected_owner)
        return _token(123)

    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(macos_login, "macos_peer_audit_token", audit)
    assert channel.capture_peer_audit_token() == _token(123)
    channel.require_live_peer()
    assert reads == ["501", "501"]


def test_darwin_token_for_another_process_refuses(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(macos_login, "macos_peer_audit_token", lambda _socket, *, expected_owner: _token(124))
    with pytest.raises(RuntimeRefusalError) as caught:
        channel.require_live_peer()
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


def test_linux_liveness_borrows_and_releases_the_peer_pidfd(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixRuntimeChannel
) -> None:
    descriptor = os.open(os.devnull, os.O_RDONLY)
    closed: list[int] = []
    checked: list[int] = []
    native_close = os.close

    def close_owned(owned: int) -> None:
        closed.append(owned)
        native_close(owned)

    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(posix, "os", SimpleNamespace(get_inheritable=os.get_inheritable, close=close_owned))
    monkeypatch.setattr(posix, "_linux_peer_pidfd", lambda _socket: descriptor)
    monkeypatch.setattr(posix, "_require_live_linux_pidfd", checked.append)
    try:
        channel.require_live_peer()
    finally:
        if not closed:
            native_close(descriptor)
    assert closed == [descriptor] and checked == [descriptor, descriptor]


def test_closed_channel_and_non_darwin_token_capture_refuse(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(RuntimeRefusalError) as caught:
        channel.capture_peer_audit_token()
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    channel.close()
    with pytest.raises(RuntimeRefusalError) as closed:
        channel.capture_peer_audit_token()
    assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
