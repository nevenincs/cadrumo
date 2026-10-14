"""Pinned POSIX peers prove liveness through their platform's exact kernel identity."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo_client.contracts.contracts import Peer, RefusalCode, RefusalError
from cadrumo_client.transport import posix_channel as posix

from .. import macos_login, native_peer
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
    return MacosPeerAuditToken(501, 501, 501, pid, 100009, 77)


@pytest.fixture
def channel(monkeypatch: pytest.MonkeyPatch) -> Iterator[posix.PosixChannel]:
    monkeypatch.setattr(posix, "_peer", lambda _socket: Peer(os_owner_id="501", process_id=123))
    connected = posix.PosixChannel(cast(socket.socket, _KernelSocket()))
    try:
        yield connected
    finally:
        connected.close()


def test_darwin_liveness_rereads_the_exact_peer_audit_token(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixChannel
) -> None:
    reads: list[str] = []

    def audit(_socket: object, *, expected_owner: str) -> MacosPeerAuditToken:
        reads.append(expected_owner)
        return _token(123)

    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(native_peer, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(macos_login, "macos_peer_audit_token", audit)
    with channel.pinned_peer_socket() as held:
        assert macos_login.macos_peer_audit_token(held, expected_owner=channel.peer.os_owner_id) == _token(123)
    native_peer.require_live_native_peer(channel)
    assert reads == ["501", "501"]


def test_darwin_token_for_another_process_refuses(monkeypatch: pytest.MonkeyPatch, channel: posix.PosixChannel) -> None:
    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(native_peer, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(macos_login, "macos_peer_audit_token", lambda _socket, *, expected_owner: _token(124))
    with pytest.raises(RefusalError) as caught:
        native_peer.require_live_native_peer(channel)
    assert caught.value.reason is RefusalCode.PEER_UNTRUSTED


def test_linux_liveness_borrows_and_releases_the_peer_pidfd(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixChannel
) -> None:
    descriptor = os.open(os.devnull, os.O_RDONLY)
    closed: list[int] = []
    checked: list[int] = []
    native_close = os.close

    def close_owned(owned: int) -> None:
        closed.append(owned)
        native_close(owned)

    monkeypatch.setattr(posix, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(native_peer, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(posix, "os", SimpleNamespace(get_inheritable=os.get_inheritable, close=close_owned))
    monkeypatch.setattr(posix, "_linux_peer_pidfd", lambda _socket: descriptor)
    monkeypatch.setattr(posix, "_require_live_linux_pidfd", checked.append)
    try:
        native_peer.require_live_native_peer(channel)
    finally:
        if not closed:
            native_close(descriptor)
    assert closed == [descriptor] and checked == [descriptor, descriptor]


def test_closed_channel_and_unsupported_native_peer_checks_refuse(
    monkeypatch: pytest.MonkeyPatch, channel: posix.PosixChannel
) -> None:
    monkeypatch.setattr(native_peer, "sys", SimpleNamespace(platform="win32"))
    with pytest.raises(RefusalError) as caught:
        native_peer.require_live_native_peer(channel)
    assert caught.value.reason is RefusalCode.CONTAINMENT_UNAVAILABLE
    channel.close()
    monkeypatch.setattr(native_peer, "sys", SimpleNamespace(platform="darwin"))
    with pytest.raises(RefusalError) as closed:
        native_peer.require_live_native_peer(channel)
    assert closed.value.reason is RefusalCode.CONNECTION_CLOSED
