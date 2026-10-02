"""Linux native login contracts, typed API failures, and explicit native prerequisites."""

from __future__ import annotations

import ctypes
import errno
import os
import socket
import struct
import sys
from collections import deque
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility

from .. import linux_login
from ..linux_gnome_lock import (
    GnomeLockBinding,
    GnomeLockState,
    gnome_user_bus_path,
    require_gnome_login_producer,
    sample_gnome_lock,
)
from ..linux_login import LinuxLoginBinding, LinuxSessionObservation, capture_linux_login

pytestmark = [pytest.mark.hex_outbound_adapter]

_BOOT = UUID("11111111-1111-4111-8111-111111111111")
_SESSION = LinuxSessionObservation("c42", 1000, 500_000, "user", "wayland", "online", False)


class _NativeFixture:
    def __init__(self) -> None:
        self.peers = deque([("c42", 1000), ("c42", 1000)])
        self.observation = _SESSION
        self.peer_calls: list[int] = []
        self.session_calls: list[str] = []
        self.failure: Exception | None = None

    def peer_session(self, pidfd: int) -> tuple[str, int]:
        self.peer_calls.append(pidfd)
        return self.peers.popleft()

    def session(self, session_id: str) -> LinuxSessionObservation:
        self.session_calls.append(session_id)
        if self.failure is not None:
            raise self.failure
        return self.observation


@pytest.fixture
def native(monkeypatch: pytest.MonkeyPatch) -> Iterator[_NativeFixture]:
    implementation = _NativeFixture()
    monkeypatch.setattr(linux_login, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(linux_login, "_NativeLogin", lambda: implementation)
    monkeypatch.setattr(linux_login, "_boot_id", lambda: _BOOT)
    monkeypatch.setattr(linux_login, "_ensure_pidfd_alive", lambda _: None)
    yield implementation


@pytest.mark.unit
def test_capture_binds_login_incarnation_and_observes_without_retaining_the_process(native: _NativeFixture) -> None:
    binding = capture_linux_login(17, expected_owner="1000")
    assert binding == LinuxLoginBinding("1000", _BOOT, "c42", 500_000)
    assert native.peer_calls == [17, 17]
    # A later observation queries that session, never a numeric PID or PIDFD.
    available = binding.observe(credential_facilities=Availability.AVAILABLE)
    unavailable = binding.observe(credential_facilities=Availability.UNAVAILABLE)
    assert available.active and unavailable.active
    assert available.unattended is unavailable.unattended is LoginEligibility.UNKNOWN
    assert available.locked and unavailable.locked
    assert available.login_id == unavailable.login_id == binding.login_id
    assert available.credential_facilities is Availability.AVAILABLE
    assert unavailable.credential_facilities is Availability.UNAVAILABLE
    assert native.peer_calls == [17, 17]
    assert native.session_calls == ["c42", "c42", "c42"]


@pytest.mark.unit
def test_both_lock_hint_values_preserve_lifetime_without_claiming_lock_integration(native: _NativeFixture) -> None:
    binding = capture_linux_login(17, expected_owner="1000")
    native.observation = replace(_SESSION, locked_hint=True, state="online")
    locked = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert locked.active and locked.locked and locked.unattended is LoginEligibility.UNKNOWN
    native.observation = replace(_SESSION, state="active")
    foreground = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert foreground.active and foreground.locked and foreground.unattended is LoginEligibility.UNKNOWN
    assert foreground.login_id == locked.login_id


@pytest.mark.parametrize(
    "changed",
    [replace(_SESSION, uid=1001), replace(_SESSION, state="closing"), replace(_SESSION, created_monotonic_usec=1)],
)
@pytest.mark.unit
def test_changed_or_closing_login_cannot_reactivate_the_binding(
    native: _NativeFixture, changed: LinuxSessionObservation
) -> None:
    binding = capture_linux_login(17, expected_owner="1000")
    native.observation = changed
    refused = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert not refused.active and refused.locked
    assert refused.unattended is LoginEligibility.INELIGIBLE
    assert refused.login_id == binding.login_id


@pytest.mark.unit
def test_boot_change_invalidates_login_without_sampling_a_new_boot_session(
    native: _NativeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding = capture_linux_login(17, expected_owner="1000")
    monkeypatch.setattr(linux_login, "_boot_id", lambda: UUID("22222222-2222-4222-8222-222222222222"))
    result = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert not result.active and result.locked and result.unattended is LoginEligibility.INELIGIBLE
    assert native.session_calls == ["c42"]


@pytest.mark.parametrize(
    "failure", [OSError(errno.ENODATA, "synthetic"), RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)]
)
@pytest.mark.parametrize("facilities", [Availability.AVAILABLE, Availability.UNAVAILABLE])
@pytest.mark.unit
def test_native_missing_or_ambiguous_evidence_is_unknown(
    native: _NativeFixture, failure: Exception, facilities: Availability
) -> None:
    binding = capture_linux_login(17, expected_owner="1000")
    native.failure = failure
    result = binding.observe(credential_facilities=facilities)
    assert not result.active and result.locked and result.unattended is LoginEligibility.UNKNOWN
    assert result.credential_facilities is facilities


@pytest.mark.parametrize("peers", [[("c42", 1001)], [("c42", 1000), ("c43", 1000)], [("c42", 1000), ("c42", 1001)]])
@pytest.mark.unit
def test_capture_refuses_owner_or_session_races(native: _NativeFixture, peers: list[tuple[str, int]]) -> None:
    native.peers = deque(peers)
    with pytest.raises(RuntimeRefusalError) as refused:
        capture_linux_login(17, expected_owner="1000")
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


@pytest.mark.unit
def test_capture_requires_live_pidfd_before_and_after_snapshot(
    native: _NativeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def died_after_snapshot(_: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    monkeypatch.setattr(linux_login, "_ensure_pidfd_alive", died_after_snapshot)
    with pytest.raises(RuntimeRefusalError):
        capture_linux_login(17, expected_owner="1000")
    assert calls == 2 and native.peer_calls == [17, 17]


@pytest.mark.parametrize(
    "changes",
    [
        {"session_class": "manager"},
        {"session_class": "greeter"},
        {"session_type": "tty"},
        {"session_type": "unspecified"},
        {"state": "unknown"},
        {"locked_hint": 0},
        {"uid": True},
        {"created_monotonic_usec": 0},
        {"session_id": "../other"},
    ],
)
@pytest.mark.unit
def test_unsupported_native_session_facts_refuse(changes: dict[str, object]) -> None:
    # Preserve deliberately defective runtime operands at this native boundary.
    invalid_native_input = cast(Callable[..., LinuxSessionObservation], replace)
    with pytest.raises(RuntimeRefusalError):
        invalid_native_input(_SESSION, **changes)


class _MessageFixture:
    """Model the typed libsystemd cursor, including containers and wrong signatures."""

    def __init__(self, events: list[tuple[object, ...]]) -> None:
        self.events = deque(events)
        self.buffers: list[ctypes.Array[ctypes.c_char]] = []

    def sd_bus_message_enter_container(self, _: object, kind: bytes, signature: bytes) -> int:
        if self.events and self.events[0] == ("enter", kind, signature):
            self.events.popleft()
            return 1
        return 0 if self.events and self.events[0] == ("exit",) else -errno.EBADMSG

    def sd_bus_message_exit_container(self, _: object) -> int:
        return 1 if self.events.popleft() == ("exit",) else -errno.EBADMSG

    def sd_bus_message_at_end(self, _: object, __: int) -> int:
        return int(not self.events or self.events[0] == ("exit",))

    def sd_bus_message_read_basic(self, _: object, kind: bytes, output: object) -> int:
        event = self.events.popleft()
        if event[:2] != ("read", kind):
            return -errno.EBADMSG
        if kind in (b"s", b"o"):
            raw = cast(bytes, event[2])
            buffer = ctypes.create_string_buffer(raw)
            self.buffers.append(buffer)
            ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(buffer)
        elif kind == b"t":
            ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_uint64))[0] = cast(int, event[2])
        else:
            ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_uint32))[0] = cast(int, event[2])
        return 1


def _properties_events(properties: list[tuple[bytes, bytes, object]]) -> list[tuple[object, ...]]:
    events: list[tuple[object, ...]] = [("enter", b"a", b"{sv}")]
    for name, signature, value in properties:
        events.extend([("enter", b"e", b"sv"), ("read", b"s", name), ("enter", b"v", signature)])
        if signature == b"(uo)":
            events.extend(
                [
                    ("enter", b"r", b"uo"),
                    ("read", b"u", value),
                    ("read", b"o", f"/org/freedesktop/login1/user/_{value}".encode()),
                    ("exit",),
                ]
            )
        else:
            events.append(("read", signature, value))
        events.extend([("exit",), ("exit",)])
    events.append(("exit",))
    return events


def _properties() -> list[tuple[bytes, bytes, object]]:
    return [
        (b"Id", b"s", b"c42"),
        (b"User", b"(uo)", 1000),
        (b"TimestampMonotonic", b"t", 500_000),
        (b"Class", b"s", b"user"),
        (b"Type", b"s", b"wayland"),
        (b"State", b"s", b"online"),
        (b"LockedHint", b"b", 0),
    ]


@pytest.mark.unit
def test_atomic_native_property_cursor_produces_only_supported_typed_evidence() -> None:
    library = _MessageFixture(_properties_events(_properties()))
    bus = linux_login._SessionBus(cast(ctypes.CDLL, library))
    assert bus.read_session_record(ctypes.c_void_p(17)).desktop() == _SESSION
    assert not library.events


@pytest.mark.parametrize(
    "defect", ["missing_lock", "wrong_lock_type", "invalid_boolean", "duplicate", "wrong_generation_type"]
)
@pytest.mark.unit
def test_native_property_cursor_refuses_missing_duplicate_or_mistyped_evidence(defect: str) -> None:
    properties = _properties()
    if defect == "missing_lock":
        properties.pop()
    elif defect == "wrong_lock_type":
        properties[-1] = (b"LockedHint", b"s", b"false")
    elif defect == "invalid_boolean":
        properties[-1] = (b"LockedHint", b"b", 2)
    elif defect == "duplicate":
        properties.append(properties[0])
    else:
        properties[2] = (b"TimestampMonotonic", b"u", 500_000)
    bus = linux_login._SessionBus(cast(ctypes.CDLL, _MessageFixture(_properties_events(properties))))
    with pytest.raises(RuntimeRefusalError):
        bus.read_session_record(ctypes.c_void_p(17)).desktop()


@pytest.mark.unit
def test_expired_aggregate_deadline_refuses_without_a_native_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    bus = linux_login._SessionBus(cast(ctypes.CDLL, object()))
    monkeypatch.setattr(linux_login.time, "monotonic", lambda: bus.deadline)
    with pytest.raises(RuntimeRefusalError):
        bus.remaining_usec()


class _AllocatedLoginFixture:
    def __init__(self, *, raw: bytes, session_result: int = 0, owner_result: int = 0) -> None:
        self.buffer = ctypes.create_string_buffer(raw)
        self.session_result = session_result
        self.owner_result = owner_result
        self.freed: list[int | None] = []
        self.descriptors: list[int] = []

    def sd_pidfd_get_session(self, descriptor: int, output: object) -> int:
        self.descriptors.append(descriptor)
        ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(self.buffer)
        return self.session_result

    def sd_pidfd_get_owner_uid(self, descriptor: int, output: object) -> int:
        self.descriptors.append(descriptor)
        ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_uint32))[0] = 1000
        return self.owner_result

    def free(self, pointer: ctypes.c_void_p) -> None:
        self.freed.append(pointer.value)


@pytest.mark.unit
@pytest.mark.parametrize("defect", ["none", "session_error", "owner_error", "invalid_id", "invalid_encoding"])
def test_pidfd_native_session_allocation_is_freed_on_success_and_all_errors(defect: str) -> None:
    library = _AllocatedLoginFixture(
        raw=b"../other" if defect == "invalid_id" else b"\xff" if defect == "invalid_encoding" else b"c42",
        session_result=-errno.ENODATA if defect == "session_error" else 0,
        owner_result=-errno.ESRCH if defect == "owner_error" else 0,
    )
    native = linux_login._NativeLogin.__new__(linux_login._NativeLogin)
    native.library = cast(ctypes.CDLL, library)
    native.libc = cast(ctypes.CDLL, library)
    if defect == "none":
        assert native.peer_session(17) == ("c42", 1000)
        assert library.descriptors == [17, 17]
    else:
        with pytest.raises((RuntimeRefusalError, UnicodeError)):
            native.peer_session(17)
    assert library.freed == [ctypes.addressof(library.buffer)]


class _CallFixture:
    def __init__(self, *, fail_at: str | None = None, sender: bytes = b":1.7") -> None:
        self.fail_at = fail_at
        self.sender = sender
        self.unreferenced: list[int | None] = []
        self.timeout: int | None = None
        self.flags: list[tuple[str, int]] = []

    def sd_bus_message_new_method_call(self, _: object, output: object, *__: object) -> int:
        ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_void_p))[0] = 11
        return -errno.ENOMEM if self.fail_at == "new" else 0

    def sd_bus_message_set_auto_start(self, _: object, value: int) -> int:
        self.flags.append(("auto_start", value))
        return 0

    def sd_bus_message_set_allow_interactive_authorization(self, _: object, value: int) -> int:
        self.flags.append(("interactive", value))
        return -errno.EINVAL if self.fail_at == "flags" else 0

    def sd_bus_message_append_basic(self, *_: object) -> int:
        return -errno.EINVAL if self.fail_at == "append" else 0

    def sd_bus_call(self, _: object, __: object, timeout: int, error: object, output: object) -> int:
        assert error is None
        self.timeout = timeout
        ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_void_p))[0] = 12
        return -errno.ETIMEDOUT if self.fail_at == "call" else 0

    def sd_bus_message_get_sender(self, _: object) -> bytes:
        return self.sender

    def sd_bus_message_unref(self, pointer: ctypes.c_void_p) -> None:
        self.unreferenced.append(pointer.value)


@pytest.mark.unit
@pytest.mark.parametrize("fail_at", [None, "new", "flags", "append", "call", "sender", "consumer"])
def test_native_call_is_nonprompting_bounded_and_releases_all_message_handles(fail_at: str | None) -> None:
    library = _CallFixture(fail_at=fail_at, sender=b":1.8" if fail_at == "sender" else b":1.7")
    bus = linux_login._SessionBus(cast(ctypes.CDLL, library))

    def invoke() -> None:
        with bus.call(b":1.7", b"/session", b"org.freedesktop.DBus.Properties", b"GetAll", b"interface") as reply:
            assert reply.value == 12
            if fail_at == "consumer":
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    if fail_at is None:
        invoke()
    else:
        with pytest.raises(RuntimeRefusalError):
            invoke()
    assert library.unreferenced == ([12, 11] if fail_at in (None, "call", "sender", "consumer") else [11])
    if fail_at != "new":
        assert library.flags == [("auto_start", 0), ("interactive", 0)]
    if library.timeout is not None:
        assert 0 < library.timeout <= 1_000_000


@pytest.mark.unit
def test_bus_daemon_lookup_cannot_accept_another_service_sender() -> None:
    library = _CallFixture(sender=b":1.7")
    bus = linux_login._SessionBus(cast(ctypes.CDLL, library))
    with (
        pytest.raises(RuntimeRefusalError),
        bus.call(
            b"org.freedesktop.DBus", b"/org/freedesktop/DBus", b"org.freedesktop.DBus", b"GetNameOwner", b"service"
        ),
    ):
        pytest.fail("foreign sender supplied a bus-daemon lookup")
    assert library.unreferenced == [12, 11]


class _ConnectionFixture:
    def __init__(self, *, uid: int = 0) -> None:
        self.uid = uid
        self.detached = False
        self.closed = False
        self.address: str | None = None

    def settimeout(self, timeout: float) -> None:
        assert 0 < timeout <= 1

    def connect(self, address: str) -> None:
        self.address = address

    def getsockopt(self, *_: object) -> bytes:
        return struct.pack("3i", 123, self.uid, self.uid)

    def setblocking(self, blocking: bool) -> None:
        assert not blocking

    def fileno(self) -> int:
        return 17

    def detach(self) -> int:
        self.detached = True
        return 17

    def close(self) -> None:
        self.closed = True


class _StartupFixture:
    def __init__(self, clock_value: list[float], *, expire: bool = False, fd_error: bool = False) -> None:
        self.clock_value = clock_value
        self.expire = expire
        self.fd_error = fd_error
        self.waits: list[int] = []
        self.closed: list[int | None] = []
        self.ready = False

    def sd_bus_new(self, output: object) -> int:
        ctypes.cast(cast(ctypes.c_void_p, output), ctypes.POINTER(ctypes.c_void_p))[0] = 21
        return 0

    def sd_bus_set_fd(self, _: object, input_fd: int, output_fd: int) -> int:
        assert input_fd == output_fd == 17
        return -errno.EINVAL if self.fd_error else 0

    def sd_bus_set_bus_client(self, _: object, enabled: int) -> int:
        assert enabled == 1
        return 0

    def sd_bus_set_method_call_timeout(self, _: object, timeout: int) -> int:
        assert 0 < timeout <= 1_000_000
        return 0

    def sd_bus_start(self, _: object) -> int:
        return 0

    def sd_bus_is_ready(self, _: object) -> int:
        return int(self.ready)

    def sd_bus_process(self, *_: object) -> int:
        return 0

    def sd_bus_wait(self, _: object, timeout: int) -> int:
        self.waits.append(timeout)
        self.clock_value[0] += 2 if self.expire else 0.25
        self.ready = True
        return 0

    def sd_bus_close_unref(self, pointer: ctypes.c_void_p) -> None:
        self.closed.append(pointer.value)


@pytest.mark.unit
@pytest.mark.parametrize("defect", [None, "untrusted_root_peer", "startup_timeout", "fd_error"])
def test_native_bus_startup_verifies_fixed_root_peer_bounds_handshake_and_closes_ownership(
    monkeypatch: pytest.MonkeyPatch, defect: str | None
) -> None:
    clock_value = [100.0]
    connection = _ConnectionFixture(uid=1000 if defect == "untrusted_root_peer" else 0)
    library = _StartupFixture(clock_value, expire=defect == "startup_timeout", fd_error=defect == "fd_error")
    monkeypatch.setattr(linux_login, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(linux_login, "Path", PurePosixPath)
    monkeypatch.setattr(linux_login, "time", SimpleNamespace(monotonic=lambda: clock_value[0]))
    monkeypatch.setattr(
        linux_login,
        "socket",
        SimpleNamespace(socket=lambda *_: connection, AF_UNIX=1, SOCK_STREAM=1, SOL_SOCKET=1, SO_PEERCRED=17),
    )
    bus = linux_login._SessionBus(cast(ctypes.CDLL, library))
    if defect is None:
        with bus:
            assert bus.remaining_usec() == 750_000
            assert connection.detached
    else:
        with pytest.raises(RuntimeRefusalError), bus:
            pytest.fail("unsupported bus startup admitted")
    assert connection.address == "/run/dbus/system_bus_socket" and connection.closed
    assert library.closed == ([] if defect == "untrusted_root_peer" else [21])
    assert connection.detached == (defect in (None, "startup_timeout"))
    assert library.waits == ([1_000_000] if defect in (None, "startup_timeout") else [])
    assert not bus.bus.value


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux PIDFD and real logind desktop session")
@pytest.mark.integration
def test_native_current_process_capture_requires_an_actual_supported_desktop() -> None:
    try:
        native = linux_login._NativeLogin()
    except (RuntimeRefusalError, OSError, AttributeError):
        pytest.skip("native libsystemd PIDFD symbols are unavailable")
    with _current_peer_pidfd() as pidfd:
        _require_native_desktop(native, pidfd)
        session_id, uid = native.peer_session(pidfd)
        prerequisite = _native_gnome_prerequisite(native, session_id=session_id, uid=uid)
        if prerequisite is not None and prerequisite[1].eligibility is not LoginEligibility.ELIGIBLE:
            pytest.skip("verified GNOME producer is currently in an incomplete lock transition")
        from ..login import capture_runtime_login
        from ..posix import PosixRuntimeChannel

        peer, runtime = socket.socketpair()
        channel = PosixRuntimeChannel(runtime)
        try:
            binding = capture_runtime_login(channel)
        finally:
            channel.close()
            peer.close()
        result = binding.observe(credential_facilities=Availability.UNAVAILABLE)
        assert isinstance(binding, LinuxLoginBinding)
        assert (binding.session_id, binding.os_owner_id) == (session_id, str(uid))
        assert native.peer_session(pidfd) == (session_id, uid)
        if prerequisite is None:
            # No independently verified same-session producer: keep the strict refusal oracle.
            assert _native_gnome_prerequisite(native, session_id=session_id, uid=uid) is None
            assert binding.gnome_lock is None
            assert result.active and result.locked and result.unattended is LoginEligibility.UNKNOWN
        else:
            expected_binding, expected_state = prerequisite
            assert binding.gnome_lock == expected_binding
            fresh = _native_gnome_prerequisite(native, session_id=session_id, uid=uid, expected=expected_binding)
            assert fresh is not None
            assert fresh == prerequisite
            assert result.active and result.unattended is LoginEligibility.ELIGIBLE
            assert result.locked == expected_state.safely_locked
        assert result.credential_facilities is Availability.UNAVAILABLE
        assert result.login_id == binding.login_id
        with pytest.raises(RuntimeRefusalError) as refused:
            capture_linux_login(pidfd, expected_owner=str(uid + 1))
        assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


def _native_gnome_prerequisite(
    native: linux_login._NativeLogin,
    *,
    session_id: str,
    uid: int,
    expected: GnomeLockBinding | None = None,
) -> tuple[GnomeLockBinding, GnomeLockState] | None:
    """Verify the actual producer independently of capture/observe's best-effort path.

    An unavailable prerequisite selects only the fail-closed branch. A verified
    producer must remain the same complete native snapshot across the test.
    """
    try:
        require_gnome_login_producer(uid)
        path = gnome_user_bus_path(uid)
        socket_identity = path.lstat()
        with linux_login._SessionBus(native.library, path=path, peer_uid=uid) as bus:
            observed = sample_gnome_lock(
                bus, uid=uid, session_id=session_id, peer_session=native.peer_session, expected=expected
            )
            require_gnome_login_producer(uid)
            if gnome_user_bus_path(uid) != path or path.lstat() != socket_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            bus.remaining_usec()
            return observed
    except RuntimeRefusalError as error:
        if error.reason is not RuntimeRefusalCode.UNAVAILABLE:
            raise
    except (OSError, AttributeError):
        pass
    return None


def _require_native_desktop(native: linux_login._NativeLogin, pidfd: int) -> None:
    """Classify test prerequisites independently of the production property parser."""
    session = ctypes.c_void_p()
    try:
        result = native.library.sd_pidfd_get_session(pidfd, ctypes.byref(session))
        if result in (-errno.ENODATA, -errno.ENOSYS, -errno.EOPNOTSUPP):
            pytest.skip("current native peer has no logind session or PIDFD login facility")
        assert result >= 0 and session.value
        identity = ctypes.cast(session, ctypes.c_char_p).value
        assert identity
        for symbol, supported in (
            ("sd_session_get_class", (b"user",)),
            ("sd_session_get_type", (b"x11", b"wayland")),
            ("sd_session_get_state", (b"online", b"active")),
        ):
            query = getattr(native.library, symbol)
            query.argtypes = (ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p))
            query.restype = ctypes.c_int
            value = ctypes.c_void_p()
            try:
                result = query(identity, ctypes.byref(value))
                if result == -errno.ENODATA:
                    pytest.skip("native session lacks the required class/type/state prerequisite")
                assert result >= 0 and value.value
                observed = ctypes.cast(value, ctypes.c_char_p).value
                if observed not in supported:
                    pytest.skip("current native session is outside active logind user x11/wayland support")
            finally:
                if value.value:
                    native.libc.free(value)
    finally:
        if session.value:
            native.libc.free(session)


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux PIDFD login APIs")
def test_native_peer_without_a_logind_session_refuses_and_keeps_borrowed_pidfd_open() -> None:
    try:
        native = linux_login._NativeLogin()
    except (RuntimeRefusalError, OSError, AttributeError):
        pytest.skip("native libsystemd PIDFD symbols are unavailable")
    with _current_peer_pidfd() as pidfd:
        session = ctypes.c_void_p()
        try:
            result = native.library.sd_pidfd_get_session(pidfd, ctypes.byref(session))
        finally:
            if session.value:
                native.libc.free(session)
        if result >= 0:
            pytest.skip("native peer belongs to a logind session; requires the no-session context")
        if result in (-errno.ENOSYS, -errno.EOPNOTSUPP):
            pytest.skip("native kernel/libsystemd PIDFD login facility is unavailable")
        assert result == -errno.ENODATA
        from ..posix import posix_owner_uid

        with pytest.raises(RuntimeRefusalError) as refused:
            capture_linux_login(pidfd, expected_owner=str(posix_owner_uid()))
        assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
        assert not os.get_inheritable(pidfd)
        os.fstat(pidfd)
        linux_login._ensure_pidfd_alive(pidfd)


@contextmanager
def _current_peer_pidfd() -> Generator[int]:
    """Acquire the test peer's kernel identity without optional numeric-PID wrappers."""
    from ..posix import _linux_peer_pidfd_option

    try:
        option = _linux_peer_pidfd_option()
    except RuntimeRefusalError as refused:
        if refused.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE:
            pytest.skip("native SO_PEERPIDFD ABI is unavailable on this architecture")
        raise
    peer, runtime = socket.socketpair()
    try:
        try:
            pidfd = runtime.getsockopt(socket.SOL_SOCKET, option)
        except OSError as error:
            if error.errno == errno.ENOPROTOOPT:
                pytest.skip("native kernel lacks SO_PEERPIDFD")
            raise
        assert type(pidfd) is int and pidfd >= 0
        try:
            yield pidfd
        finally:
            os.close(pidfd)
    finally:
        runtime.close()
        peer.close()


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux fixed system bus")
def test_native_fixed_system_bus_handshake_and_nonexistent_session_refuse() -> None:
    try:
        native = linux_login._NativeLogin()
    except (RuntimeRefusalError, OSError, AttributeError):
        pytest.skip("required native libsystemd API symbols are unavailable")
    try:
        os.stat("/run/dbus/system_bus_socket")
    except FileNotFoundError:
        pytest.skip("native fixed system bus socket is absent")
    with linux_login._SessionBus(native.library) as bus:
        # This independently exercises real startup and the bus-daemon C call.
        # The synthetic requested name is guaranteed to be a valid bus name.
        with bus.call(
            b"org.freedesktop.DBus",
            b"/org/freedesktop/DBus",
            b"org.freedesktop.DBus",
            b"GetNameOwner",
            b"org.freedesktop.DBus",
        ) as reply:
            assert bus.read_string(reply, b"s") == b"org.freedesktop.DBus"
            bus.require_end(reply)
        with (
            pytest.raises(RuntimeRefusalError),
            bus.call(
                b"org.freedesktop.DBus",
                b"/org/freedesktop/DBus",
                b"org.freedesktop.DBus",
                b"GetNameOwner",
                f"org.cadrumo.Nonexistent{uuid4().hex}".encode(),
            ),
        ):
            pytest.fail("synthetic service unexpectedly exists")
    assert not bus.bus.value
    with pytest.raises(RuntimeRefusalError) as refused:
        native.session(f"cadrumo{uuid4().hex}")
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE


class _InventoryPort:
    """Explicit native scheduling port; production inventory algorithm is real."""

    def __init__(self) -> None:
        self.deadline = 0.0
        self.clock = 100.0
        self.closed = False
        self.owner = b":1.7"
        self.root_uid = 0
        self.table: tuple[linux_login._SessionReference, ...] = (
            linux_login._SessionReference("c42", 1000, b"/org/freedesktop/login1/session/c42"),
        )
        self.tables: deque[tuple[linux_login._SessionReference, ...]] = deque()
        self.records = {"c42": linux_login._SessionRecord("c42", 1000, 500_000, "user", "wayland", "online", False)}
        self.later: dict[str, linux_login._SessionRecord] = {}
        self.calls: list[str] = []
        self.producer = "c42"
        self.locked = False
        self.expire = False
        self.change_owner = False
        self.failure = False

    def __enter__(self) -> _InventoryPort:
        return self

    def __exit__(self, *_: object) -> None:
        self.closed = True

    def remaining_usec(self) -> int:
        remaining = int((self.deadline - self.clock) * 1_000_000)
        if remaining <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return remaining

    def login_owner(self) -> bytes:
        return b":1.8" if self.change_owner and self.calls else self.owner

    @contextmanager
    def call(
        self, _destination: bytes, _path: bytes, _interface: bytes, method: bytes, _argument: bytes | None = None
    ) -> Generator[ctypes.c_void_p]:
        assert method == b"GetConnectionUnixUser"
        yield ctypes.c_void_p(1)

    def read_integer(self, _reply: ctypes.c_void_p, kind: bytes) -> int:
        assert kind == b"u"
        return self.root_uid

    def require_end(self, _reply: ctypes.c_void_p) -> None:
        pass

    def sessions(self, _owner: bytes) -> tuple[linux_login._SessionReference, ...]:
        return self.tables.popleft() if self.tables else self.table

    def session_record(self, _owner: bytes, session_id: str, *, expected_path: bytes) -> linux_login._SessionRecord:
        assert expected_path.endswith(session_id.encode())
        self.calls.append(session_id)
        if self.failure:
            raise OSError(errno.EACCES, "synthetic native denial")
        if self.calls.count(session_id) > 1 and session_id in self.later:
            return self.later[session_id]
        return self.records[session_id]


@pytest.fixture
def inventory_port(monkeypatch: pytest.MonkeyPatch) -> _InventoryPort:
    port = _InventoryPort()
    monkeypatch.setattr(linux_login, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(linux_login, "posix_owner_uid", lambda: 1000)
    monkeypatch.setattr(linux_login, "time", SimpleNamespace(monotonic=lambda: port.clock))
    monkeypatch.setattr(linux_login, "_boot_id", lambda: _BOOT)
    monkeypatch.setattr(linux_login, "_NativeLogin", lambda: SimpleNamespace(library=object()))

    def open_bus(_library: object, *, deadline: float) -> _InventoryPort:
        port.deadline = deadline
        return port

    def sample(
        _native: object, session_id: str, uid: int, *, deadline: float
    ) -> tuple[GnomeLockBinding, GnomeLockState]:
        assert uid == 1000 and deadline == port.deadline == 101.0
        if port.expire:
            port.clock = deadline
        if session_id != port.producer:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return (
            GnomeLockBinding(b"a" * 32, b":1.9", 42, _BOOT),
            GnomeLockState(_BOOT, 1, port.locked, port.locked, "unlock-dialog" if port.locked else "user"),
        )

    monkeypatch.setattr(linux_login, "_SessionBus", open_bus)
    monkeypatch.setattr(linux_login, "_gnome_observation", sample)
    return port


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["empty", "foreign", "manager", "tty", "closing"])
def test_owner_inventory_proves_absence_only_from_complete_native_facts(
    inventory_port: _InventoryPort, kind: str
) -> None:
    port = inventory_port
    if kind == "empty":
        port.table = ()
    elif kind == "foreign":
        port.table = (replace(port.table[0], uid=1001),)
    else:
        if kind == "manager":
            port.records["c42"] = replace(port.records["c42"], session_class="manager", session_type="unspecified")
        elif kind == "tty":
            port.records["c42"] = replace(port.records["c42"], session_type="tty")
        else:
            port.records["c42"] = replace(port.records["c42"], state="closing")
    result = linux_login.linux_login_inventory(expected_owner="1000")
    assert result.complete and result.logins == ()
    assert result.eligibility is LoginEligibility.INELIGIBLE
    assert port.closed
    if kind in ("empty", "foreign"):
        assert port.calls == []
    else:
        assert port.calls == ["c42", "c42"]


@pytest.mark.unit
@pytest.mark.parametrize("locked", [False, True])
def test_owner_inventory_returns_exact_desktop_and_verified_lock_producer(
    inventory_port: _InventoryPort, locked: bool
) -> None:
    port = inventory_port
    port.locked = locked
    result = linux_login.linux_login_inventory(expected_owner="1000")
    assert result.complete and result.eligibility is LoginEligibility.ELIGIBLE
    assert result.logins == (
        LinuxLoginBinding("1000", _BOOT, "c42", 500_000, GnomeLockBinding(b"a" * 32, b":1.9", 42, _BOOT)),
    )
    assert port.calls == ["c42", "c42"] and port.closed


@pytest.mark.unit
@pytest.mark.parametrize(
    "defect",
    [
        "unknown_class",
        "unknown_type",
        "unknown_state",
        "unknown_class_with_tty",
        "producer",
        "native",
        "reuse",
        "table",
        "owner",
        "root_peer",
        "deadline",
        "boot",
    ],
)
def test_owner_inventory_uncertain_native_rows_or_incarnations_never_prove_absence(
    inventory_port: _InventoryPort, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    port = inventory_port
    if defect.startswith("unknown_"):
        if defect == "unknown_class_with_tty":
            port.records["c42"] = replace(port.records["c42"], session_class="future", session_type="tty")
        elif defect == "unknown_class":
            port.records["c42"] = replace(port.records["c42"], session_class="future")
        elif defect == "unknown_type":
            port.records["c42"] = replace(port.records["c42"], session_type="future")
        else:
            port.records["c42"] = replace(port.records["c42"], state="future")
    elif defect == "producer":
        port.producer = "other-login"
    elif defect == "native":
        port.failure = True
    elif defect == "reuse":
        port.later["c42"] = replace(port.records["c42"], created_monotonic_usec=600_000)
    elif defect == "table":
        port.tables.extend((port.table, ()))
    elif defect == "owner":
        port.change_owner = True
    elif defect == "root_peer":
        port.root_uid = 1000
    elif defect == "deadline":
        port.expire = True
    else:
        boots = iter((_BOOT, UUID("22222222-2222-4222-8222-222222222222")))
        monkeypatch.setattr(linux_login, "_boot_id", lambda: next(boots))
    result = linux_login.linux_login_inventory(expected_owner="1000")
    assert not result.complete and not result.logins
    assert result.eligibility is LoginEligibility.UNKNOWN and port.closed


@pytest.mark.unit
def test_owner_inventory_does_not_assign_one_shell_producer_to_another_desktop(inventory_port: _InventoryPort) -> None:
    port = inventory_port
    port.table += (linux_login._SessionReference("c43", 1000, b"/org/freedesktop/login1/session/c43"),)
    port.records["c43"] = replace(port.records["c42"], session_id="c43", created_monotonic_usec=600_000)
    result = linux_login.linux_login_inventory(expected_owner="1000")
    assert not result.complete and result.eligibility is LoginEligibility.ELIGIBLE
    assert (
        len(result.logins) == 1
        and result.logins[0].login_id == LinuxLoginBinding("1000", _BOOT, "c42", 500_000).login_id
    )
    assert port.calls == ["c42", "c42", "c43"] and port.closed


def _session_table_events(rows: tuple[tuple[bytes, int, bytes], ...]) -> list[tuple[object, ...]]:
    events: list[tuple[object, ...]] = [("enter", b"a", b"(susso)")]
    for identity, uid, path in rows:
        events.extend(
            (
                ("enter", b"r", b"susso"),
                ("read", b"s", identity),
                ("read", b"u", uid),
                ("read", b"s", b"discarded-account"),
                ("read", b"s", b""),
                ("read", b"o", path),
                ("exit",),
            )
        )
    events.append(("exit",))
    return events


@pytest.mark.unit
@pytest.mark.parametrize("defect", [None, "duplicate", "duplicate_path", "path", "uid", "count", "signature"])
def test_native_owner_table_cursor_is_bounded_exact_and_rejects_ambiguous_rows(defect: str | None) -> None:
    row = (b"c42", 1000, b"/org/freedesktop/login1/session/c42")
    rows = (row,)
    if defect == "duplicate":
        rows += (row,)
    elif defect == "duplicate_path":
        rows += ((b"c43", 1000, row[2]),)
    elif defect == "path":
        rows = ((b"c42", 1000, b"/untrusted"),)
    elif defect == "uid":
        rows = ((b"c42", 0xFFFFFFFF, row[2]),)
    elif defect == "count":
        rows = tuple(
            (f"c{index}".encode(), 1000, f"/org/freedesktop/login1/session/c{index}".encode())
            for index in range(linux_login._SESSION_LIMIT + 1)
        )
    events = _session_table_events(rows)
    if defect == "signature":
        events[1] = ("enter", b"r", b"ssuso")
    library = _MessageFixture(events)
    bus = linux_login._SessionBus(cast(ctypes.CDLL, library))
    if defect is None:
        assert bus.read_sessions(ctypes.c_void_p(17)) == (linux_login._SessionReference("c42", 1000, row[2]),)
        assert not library.events
    else:
        with pytest.raises(RuntimeRefusalError):
            bus.read_sessions(ctypes.c_void_p(17))


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["manager", "tty", "closing"])
def test_native_property_parser_keeps_noninteractive_facts_separate_from_desktop_admission(kind: str) -> None:
    values = _properties()
    index, value = {"manager": (3, b"manager"), "tty": (4, b"tty"), "closing": (5, b"closing")}[kind]
    name, signature, _ = values[index]
    values[index] = (name, signature, value)
    bus = linux_login._SessionBus(cast(ctypes.CDLL, _MessageFixture(_properties_events(values))))
    record = bus.read_session_record(ctypes.c_void_p(17))
    assert record.known_ineligible and record.session_id == "c42" and record.uid == 1000
    if kind != "closing":
        with pytest.raises(RuntimeRefusalError):
            record.desktop()
    else:
        assert record.desktop().state == "closing"
