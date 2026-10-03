"""Socket-derived POSIX login capture pins native evidence across capture."""

from __future__ import annotations

import errno
import os
import socket
import struct
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext

from .. import linux_login, macos_login, posix_channel
from ..macos_login import MacosLoginBinding, MacosSessionObservation
from ..posix_channel import PosixRuntimeChannel

pytestmark = pytest.mark.hex_outbound_adapter


@dataclass(frozen=True)
class _LoginEvidence:
    login_id: str = "synthetic-linux-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id="synthetic-owner",
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


class _KernelSocket:
    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        return -1 if self.closed else 42

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def channel(monkeypatch: pytest.MonkeyPatch) -> Iterator[PosixRuntimeChannel]:
    monkeypatch.setattr(
        posix_channel, "_peer", lambda _socket: RuntimePeer(os_owner_id="synthetic-owner", process_id=123)
    )
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="linux"))
    connected = PosixRuntimeChannel(cast(socket.socket, _KernelSocket()))
    try:
        yield connected
    finally:
        connected.close()


@pytest.fixture
def peer_fd(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[int, list[int]]]:
    descriptor = os.open(os.devnull, os.O_RDONLY)
    closed: list[int] = []
    native_close = os.close

    def close_owned(owned: int) -> None:
        closed.append(owned)
        native_close(owned)

    monkeypatch.setattr(posix_channel, "os", SimpleNamespace(get_inheritable=os.get_inheritable, close=close_owned))
    monkeypatch.setattr(posix_channel, "_linux_peer_pidfd", lambda _socket: descriptor)
    monkeypatch.setattr(posix_channel, "_require_live_linux_pidfd", lambda _descriptor: None)
    try:
        yield descriptor, closed
    finally:
        if not closed:
            native_close(descriptor)


@pytest.mark.unit
def test_capture_borrows_noninheritable_fd_then_closes_once(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel, peer_fd: tuple[int, list[int]]
) -> None:
    descriptor, closed = peer_fd
    evidence = _LoginEvidence()

    def capture(held: int, *, expected_owner: str) -> _LoginEvidence:
        assert held == descriptor
        assert expected_owner == channel.peer.os_owner_id
        assert not os.get_inheritable(held)
        os.fstat(held)
        return evidence

    monkeypatch.setattr(linux_login, "capture_linux_login", capture)
    assert channel.capture_login() is evidence
    assert closed == [descriptor]
    with pytest.raises(OSError):
        os.fstat(descriptor)


@pytest.mark.unit
@pytest.mark.parametrize("failure_at", ["before", "helper", "after"])
def test_capture_refusal_releases_fd_and_preserves_reason(
    failure_at: str,
    monkeypatch: pytest.MonkeyPatch,
    channel: PosixRuntimeChannel,
    peer_fd: tuple[int, list[int]],
) -> None:
    descriptor, closed = peer_fd
    checks = 0
    helper_calls = 0

    def alive(_held: int) -> None:
        nonlocal checks
        checks += 1
        if (failure_at == "before" and checks == 1) or (failure_at == "after" and checks == 2):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    def capture(_held: int, *, expected_owner: str) -> _LoginEvidence:
        nonlocal helper_calls
        helper_calls += 1
        assert expected_owner == channel.peer.os_owner_id
        if failure_at == "helper":
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return _LoginEvidence()

    monkeypatch.setattr(posix_channel, "_require_live_linux_pidfd", alive)
    monkeypatch.setattr(linux_login, "capture_linux_login", capture)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert closed == [descriptor]
    assert helper_calls == (0 if failure_at == "before" else 1)
    assert checks == (2 if failure_at == "after" else 1)


@pytest.mark.unit
def test_inheritable_fd_refuses_before_login_helper(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel, peer_fd: tuple[int, list[int]]
) -> None:
    descriptor, closed = peer_fd
    os.set_inheritable(descriptor, True)

    def unexpected_capture(_held: int, *, expected_owner: str) -> _LoginEvidence:
        pytest.fail(f"inheritable descriptor reached login capture for {expected_owner}")

    monkeypatch.setattr(linux_login, "capture_linux_login", unexpected_capture)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert closed == [descriptor]


@pytest.mark.unit
def test_reentrant_close_refuses_captured_evidence_and_releases_fd(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel, peer_fd: tuple[int, list[int]]
) -> None:
    descriptor, closed = peer_fd

    def capture(_held: int, *, expected_owner: str) -> _LoginEvidence:
        assert expected_owner == channel.peer.os_owner_id
        channel.close()
        return _LoginEvidence()

    monkeypatch.setattr(linux_login, "capture_linux_login", capture)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert closed == [descriptor]


@pytest.mark.unit
def test_native_fd_inspection_failure_releases_owned_fd(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel, peer_fd: tuple[int, list[int]]
) -> None:
    descriptor, closed = peer_fd

    def unavailable(_held: int) -> bool:
        raise OSError(errno.EBADF, "synthetic native inspection failure")

    monkeypatch.setattr(posix_channel.os, "get_inheritable", unavailable)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert "synthetic" not in str(refused.value)
    assert closed == [descriptor]


@pytest.mark.unit
def test_close_waits_for_capture_and_fd_release(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel, peer_fd: tuple[int, list[int]]
) -> None:
    descriptor, closed = peer_fd
    entered, release, closing = Event(), Event(), Event()

    def capture(_held: int, *, expected_owner: str) -> _LoginEvidence:
        assert expected_owner == channel.peer.os_owner_id
        entered.set()
        assert release.wait(timeout=5)
        os.fstat(descriptor)
        assert closed == []
        return _LoginEvidence()

    def close_channel() -> None:
        closing.set()
        channel.close()
        assert closed == [descriptor]

    monkeypatch.setattr(linux_login, "capture_linux_login", capture)
    with ThreadPoolExecutor(max_workers=2) as pool:
        capturing = pool.submit(channel.capture_login)
        try:
            assert entered.wait(timeout=5)
            close_future = pool.submit(close_channel)
            assert closing.wait(timeout=5)
            assert not close_future.done()
        finally:
            release.set()
        assert capturing.result(timeout=5).login_id == "synthetic-linux-login"
        close_future.result(timeout=5)
    assert closed == [descriptor]
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED


@pytest.mark.unit
def test_unsupported_platform_refuses_private_capture_without_socket_option(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="win32"))
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.unit
def test_darwin_capture_passes_held_socket_and_owner_without_granting_eligibility(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="darwin"))
    binding = MacosLoginBinding(os_owner_id="synthetic-owner", audit_session_id=100022)
    observed: list[tuple[socket.socket, str]] = []

    def capture(held: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
        observed.append((held, expected_owner))
        assert held is channel._socket
        assert held.fileno() == 42
        return binding

    monkeypatch.setattr(macos_login, "capture_macos_login", capture)
    monkeypatch.setattr(
        macos_login,
        "observe_macos_session",
        lambda session_id: MacosSessionObservation(session_id, 0x10),
    )

    captured = channel.capture_login()
    assert captured is binding
    assert observed == [(channel._socket, "synthetic-owner")]
    context = captured.observe(credential_facilities=Availability.AVAILABLE)
    assert context.active and context.locked
    assert context.unattended is LoginEligibility.UNKNOWN


@pytest.mark.unit
def test_darwin_closed_channel_never_calls_native_capture(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="darwin"))
    calls = 0

    def unexpected_capture(_held: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
        nonlocal calls
        calls += 1
        pytest.fail(f"closed channel reached native capture for {expected_owner}")

    monkeypatch.setattr(macos_login, "capture_macos_login", unexpected_capture)
    channel.close()
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert calls == 0


@pytest.mark.unit
def test_darwin_helper_refusal_is_preserved(monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="darwin"))

    def refuse(_held: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
        assert expected_owner == "synthetic-owner"
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    monkeypatch.setattr(macos_login, "capture_macos_login", refuse)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert channel._socket.fileno() == 42


@pytest.mark.unit
def test_darwin_reentrant_close_prevents_releasing_captured_evidence(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="darwin"))
    binding = MacosLoginBinding(os_owner_id="synthetic-owner", audit_session_id=100022)

    def capture(held: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
        assert held is channel._socket
        assert expected_owner == "synthetic-owner"
        channel.close()
        return binding

    monkeypatch.setattr(macos_login, "capture_macos_login", capture)
    with pytest.raises(RuntimeRefusalError) as refused:
        channel.capture_login()
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert channel._socket.fileno() == -1


@pytest.mark.unit
def test_darwin_close_waits_until_native_capture_completes(
    monkeypatch: pytest.MonkeyPatch, channel: PosixRuntimeChannel
) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="darwin"))
    binding = MacosLoginBinding(os_owner_id="synthetic-owner", audit_session_id=100022)
    entered, release, closing = Event(), Event(), Event()
    observed: list[tuple[socket.socket, str]] = []

    def capture(held: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
        observed.append((held, expected_owner))
        assert held is channel._socket
        assert held.fileno() == 42
        entered.set()
        assert release.wait(timeout=5)
        assert held.fileno() == 42
        return binding

    def close_channel() -> None:
        closing.set()
        channel.close()

    monkeypatch.setattr(macos_login, "capture_macos_login", capture)
    with ThreadPoolExecutor(max_workers=2) as pool:
        capturing = pool.submit(channel.capture_login)
        try:
            assert entered.wait(timeout=5)
            close_future = pool.submit(close_channel)
            assert closing.wait(timeout=5)
            assert not close_future.done()
        finally:
            release.set()
        assert capturing.result(timeout=5) is binding
        close_future.result(timeout=5)
    assert observed == [(channel._socket, "synthetic-owner")]
    assert channel._socket.fileno() == -1


@pytest.mark.unit
@pytest.mark.parametrize("machine", ["x86_64", "aarch64", "sparc64"])
def test_absent_python_constant_only_uses_verified_generic_abis(machine: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(posix_channel, "socket", SimpleNamespace())
    monkeypatch.setattr(posix_channel, "platform", SimpleNamespace(machine=lambda: machine))
    if machine == "sparc64":
        with pytest.raises(RuntimeRefusalError) as refused:
            posix_channel._linux_peer_pidfd_option()
        assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    else:
        assert posix_channel._linux_peer_pidfd_option() == 77


@pytest.mark.unit
def test_exposed_socket_constant_supports_other_kernel_abis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(posix_channel, "socket", SimpleNamespace(SO_PEERPIDFD=86))
    monkeypatch.setattr(posix_channel, "platform", SimpleNamespace(machine=lambda: "sparc64"))
    assert posix_channel._linux_peer_pidfd_option() == 86


@pytest.mark.unit
def test_missing_kernel_option_refuses_without_numeric_pid_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class MissingKernelOption:
        def getsockopt(self, level: int, option: int) -> int:
            assert level == socket.SOL_SOCKET and option == 77
            raise OSError(errno.ENOPROTOOPT, "synthetic unavailable facility")

    monkeypatch.setattr(posix_channel, "_linux_peer_pidfd_option", lambda: 77)
    with pytest.raises(RuntimeRefusalError) as refused:
        posix_channel._linux_peer_pidfd(cast(socket.socket, MissingKernelOption()))
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert "synthetic" not in str(refused.value)


@pytest.mark.unit
def test_native_poll_reports_peer_death_without_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    class KernelPoll:
        def register(self, descriptor: int, events: int) -> None:
            assert descriptor == 123
            assert events == 1 | 8 | 16

        def poll(self, timeout: int) -> list[tuple[int, int]]:
            assert timeout == 0
            return [(123, 1)]

    monkeypatch.setattr(posix_channel, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(posix_channel, "select", SimpleNamespace(poll=KernelPoll, POLLIN=1, POLLERR=8, POLLHUP=16))
    with pytest.raises(RuntimeRefusalError) as refused:
        posix_channel._require_live_linux_pidfd(123)
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux SO_PEERPIDFD")
def test_native_kernel_pidfd_is_caller_owned_and_noninheritable() -> None:
    left, right = socket.socketpair()
    try:
        descriptor = _native_peer_pidfd(left)
        try:
            assert not os.get_inheritable(descriptor)
            posix_channel._require_live_linux_pidfd(descriptor)
            with open(f"/proc/self/fdinfo/{descriptor}", encoding="ascii") as information:
                lines = information.read().splitlines()
            assert f"Pid:\t{os.getpid()}" in lines
            left.close()
            # The socket and returned PIDFD have independent ownership.
            os.fstat(descriptor)
            posix_channel._require_live_linux_pidfd(descriptor)
        finally:
            os.close(descriptor)
        with pytest.raises(OSError) as released:
            os.fstat(descriptor)
        assert released.value.errno == errno.EBADF
    finally:
        left.close()
        right.close()


def _native_peer_pidfd(connected: socket.socket) -> int:
    # Distinguish a missing kernel option before exercising the owning getter;
    # its other failures must remain test failures, not capability skips.
    try:
        probe = connected.getsockopt(socket.SOL_SOCKET, posix_channel._linux_peer_pidfd_option())
    except OSError as error:
        if error.errno == errno.ENOPROTOOPT:
            pytest.skip("native kernel lacks SO_PEERPIDFD; kernel acceptance unavailable")
        raise
    os.close(probe)
    return posix_channel._linux_peer_pidfd(connected)


def _child_connect_and_transfer(address: str, control: socket.socket) -> None:
    """Let a native child connect, transfer its stream, and exit on parent command."""
    if sys.platform == "linux":
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connected:
                connected.settimeout(5)
                control.settimeout(5)
                connected.connect(address)
                control.sendmsg([b"F"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", connected.fileno()))])
                if control.recv(1) != b"X":
                    os._exit(2)
            os._exit(0)
        except BaseException:
            os._exit(3)
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux fork, SCM_RIGHTS, and SO_PEERPIDFD")
def test_native_kernel_pidfd_detects_original_peer_exit_with_transferred_stream_open() -> None:
    if sys.platform != "linux":
        pytest.fail("native Linux test selected on an unsupported host")
    parent_control, child_control = socket.socketpair()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    address = "\0cadrumo-pidfd-test-" + uuid4().hex
    descriptor: int | None = None
    retained: socket.socket | None = None
    accepted: socket.socket | None = None
    process_id: int | None = None
    reaped = False
    try:
        listener.bind(address)
        listener.listen(1)
        listener.settimeout(5)
        parent_control.settimeout(5)
        process_id = os.fork()
        if process_id == 0:
            listener.close()
            parent_control.close()
            _child_connect_and_transfer(address, child_control)
            os._exit(4)
        child_control.close()
        accepted, _ = listener.accept()
        payload, ancillary, flags, _ = parent_control.recvmsg(1, socket.CMSG_SPACE(struct.calcsize("i")))
        assert payload == b"F" and not flags
        assert len(ancillary) == 1
        level, kind, packed = ancillary[0]
        assert level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS
        retained = socket.socket(fileno=struct.unpack("i", packed)[0])
        peer_pid, peer_uid, _ = posix_channel._linux_peer_credentials(accepted)
        assert peer_pid == process_id and peer_uid == os.getuid()
        descriptor = _native_peer_pidfd(accepted)
        posix_channel._require_live_linux_pidfd(descriptor)
        parent_control.sendall(b"X")
        exited, status = os.waitpid(process_id, 0)
        reaped = True
        assert exited == process_id and os.waitstatus_to_exitcode(status) == 0
        # A transferred stream keeps the transport alive after its original
        # kernel credential process exits. PIDFD liveness must still refuse.
        retained.sendall(b"R")
        assert accepted.recv(1) == b"R"
        with pytest.raises(RuntimeRefusalError) as refused:
            posix_channel._require_live_linux_pidfd(descriptor)
        assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    finally:
        parent_control.close()
        child_control.close()
        listener.close()
        if accepted is not None:
            accepted.close()
        if retained is not None:
            retained.close()
        if descriptor is not None:
            os.close(descriptor)
        if process_id is not None and process_id > 0 and not reaped:
            # Closing the parent control wakes the child's bounded read.
            os.waitpid(process_id, 0)
