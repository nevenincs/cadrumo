"""PIDFD-bound logind provenance and fresh lifetime observations of one login.

Logind's LockedHint cannot prove that a desktop reliably reports lock events.
Only an explicitly provisioned same-owner GNOME observer establishes reliable
lock integration. A user manager, TTY, or process outside an actual desktop
login supplies no supported native provenance.
"""

from __future__ import annotations

import ctypes
import os
import re
import select
import socket
import struct
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginInventory
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from .linux_gnome_lock import (
    GnomeLockBinding,
    GnomeLockState,
    gnome_user_bus_path,
    require_gnome_login_producer,
    sample_gnome_lock,
)
from .posix import posix_owner_uid

_LOGIN_DESTINATION = b"org.freedesktop.login1"
_LOGIN_MANAGER = b"/org/freedesktop/login1"
_SESSION_INTERFACE = b"org.freedesktop.login1.Session"
_BUS_DESTINATION = b"org.freedesktop.DBus"
_BUS_PATH = b"/org/freedesktop/DBus"
_BUS_TIMEOUT_SECONDS = 1.0
_SESSION_LIMIT = 128
_SESSION_ID = re.compile(r"[A-Za-z0-9_]{1,64}\Z", re.ASCII)
_UNIQUE_OWNER = re.compile(rb":[0-9]+\.[0-9]+\Z", re.ASCII)
_SESSION_PATH = re.compile(rb"/org/freedesktop/login1/session/[A-Za-z0-9_]{1,192}\Z", re.ASCII)
_PROPERTY_SIGNATURES = {
    "Id": b"s",
    "User": b"(uo)",
    "TimestampMonotonic": b"t",
    "Class": b"s",
    "Type": b"s",
    "State": b"s",
    "LockedHint": b"b",
}


def _unavailable() -> RuntimeRefusalError:
    return RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _check(result: int, *, required: bool = False) -> None:
    if result < 0 or (required and result == 0):
        raise _unavailable()


def _boot_id() -> UUID:
    with open("/proc/sys/kernel/random/boot_id", "rb") as source:
        value = source.read(38)
    if len(value) != 37 or value[-1:] != b"\n":
        raise _unavailable()
    identity = UUID(value[:-1].decode("ascii"))
    if identity.int == 0 or str(identity).encode("ascii") != value[:-1]:
        raise _unavailable()
    return identity


def _ensure_pidfd_alive(pidfd: int) -> None:
    if sys.platform == "linux":
        if type(pidfd) is not int or pidfd < 0 or os.get_inheritable(pidfd):
            raise _unavailable()
        poller = select.poll()
        poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if poller.poll(0):
            raise _unavailable()
        return
    raise _unavailable()


@dataclass(frozen=True)
class LinuxSessionObservation:
    """Minimal typed native snapshot; account names and remote data are discarded."""

    session_id: str
    uid: int
    created_monotonic_usec: int
    session_class: str
    session_type: str
    state: str
    locked_hint: bool

    def __post_init__(self) -> None:
        """Reject unsupported or malformed native facts before they become evidence."""
        if (
            type(self.session_id) is not str
            or not _SESSION_ID.fullmatch(self.session_id)
            or type(self.uid) is not int
            or not 0 <= self.uid < 0xFFFFFFFF
            or type(self.created_monotonic_usec) is not int
            or not 0 < self.created_monotonic_usec < 0xFFFFFFFFFFFFFFFF
            or self.session_class != "user"
            or self.session_type not in ("x11", "wayland")
            or self.state not in ("active", "online", "closing")
            or type(self.locked_hint) is not bool
        ):
            raise _unavailable()


@dataclass(frozen=True)
class _SessionRecord:
    """Typed native properties before supported-desktop admission is decided."""

    session_id: str
    uid: int
    created_monotonic_usec: int
    session_class: str
    session_type: str
    state: str
    locked_hint: bool

    def __post_init__(self) -> None:
        if (
            type(self.session_id) is not str
            or not _SESSION_ID.fullmatch(self.session_id)
            or type(self.uid) is not int
            or not 0 <= self.uid < 0xFFFFFFFF
            or type(self.created_monotonic_usec) is not int
            or not 0 < self.created_monotonic_usec < 0xFFFFFFFFFFFFFFFF
            or any(
                type(value) is not str or not 1 <= len(value) <= 64 or not value.isascii()
                for value in (self.session_class, self.session_type, self.state)
            )
            or type(self.locked_hint) is not bool
        ):
            raise _unavailable()

    def desktop(self) -> LinuxSessionObservation:
        """Keep the original class=user, x11/wayland admission unchanged."""
        return LinuxSessionObservation(
            self.session_id,
            self.uid,
            self.created_monotonic_usec,
            self.session_class,
            self.session_type,
            self.state,
            self.locked_hint,
        )

    @property
    def known_ineligible(self) -> bool:
        """Exclude only exact closing or positively noninteractive native facts."""
        noninteractive = ("manager", "manager-early", "background", "background-light", "greeter", "lock-screen")
        if (
            self.session_class not in ("user", *noninteractive)
            or self.session_type not in ("x11", "wayland", "tty", "mir", "unspecified")
            or self.state not in ("online", "active", "closing")
        ):
            return False
        return self.state == "closing" or (
            self.state in ("online", "active") and (self.session_class in noninteractive or self.session_type == "tty")
        )


@dataclass(frozen=True)
class _SessionReference:
    session_id: str
    uid: int
    object_path: bytes

    def __post_init__(self) -> None:
        if (
            type(self.session_id) is not str
            or not _SESSION_ID.fullmatch(self.session_id)
            or type(self.uid) is not int
            or not 0 <= self.uid < 0xFFFFFFFF
            or type(self.object_path) is not bytes
            or not _SESSION_PATH.fullmatch(self.object_path)
        ):
            raise _unavailable()


class _NativeLogin:
    """Fixed native APIs; PID/peer sd-login functions are never used for authority."""

    library: ctypes.CDLL
    libc: ctypes.CDLL

    def __init__(self) -> None:
        if sys.platform != "linux":
            raise _unavailable()
        self.library = ctypes.CDLL("libsystemd.so.0")
        self.libc = ctypes.CDLL("libc.so.6")
        self.libc.free.argtypes = (ctypes.c_void_p,)
        self.libc.free.restype = None
        pointer = ctypes.c_void_p
        output = ctypes.POINTER(pointer)
        signatures = {
            "sd_pidfd_get_session": ((ctypes.c_int, output), ctypes.c_int),
            "sd_pidfd_get_owner_uid": ((ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int),
            "sd_bus_new": ((output,), ctypes.c_int),
            "sd_bus_set_fd": ((pointer, ctypes.c_int, ctypes.c_int), ctypes.c_int),
            "sd_bus_set_bus_client": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_set_method_call_timeout": ((pointer, ctypes.c_uint64), ctypes.c_int),
            "sd_bus_start": ((pointer,), ctypes.c_int),
            "sd_bus_is_ready": ((pointer,), ctypes.c_int),
            "sd_bus_process": ((pointer, output), ctypes.c_int),
            "sd_bus_wait": ((pointer, ctypes.c_uint64), ctypes.c_int),
            "sd_bus_close_unref": ((pointer,), pointer),
            "sd_bus_message_new_method_call": (
                (pointer, output, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p),
                ctypes.c_int,
            ),
            "sd_bus_message_set_auto_start": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_set_allow_interactive_authorization": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_append_basic": ((pointer, ctypes.c_char, pointer), ctypes.c_int),
            "sd_bus_call": ((pointer, pointer, ctypes.c_uint64, pointer, output), ctypes.c_int),
            "sd_bus_message_unref": ((pointer,), pointer),
            "sd_bus_message_get_sender": ((pointer,), ctypes.c_char_p),
            "sd_bus_message_read_basic": ((pointer, ctypes.c_char, pointer), ctypes.c_int),
            "sd_bus_message_enter_container": ((pointer, ctypes.c_char, ctypes.c_char_p), ctypes.c_int),
            "sd_bus_message_exit_container": ((pointer,), ctypes.c_int),
            "sd_bus_message_at_end": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_skip": ((pointer, ctypes.c_char_p), ctypes.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.library, name)
            function.argtypes = arguments
            function.restype = result

    def peer_session(self, pidfd: int) -> tuple[str, int]:
        session = ctypes.c_void_p()
        uid = ctypes.c_uint32()
        try:
            _check(self.library.sd_pidfd_get_session(pidfd, ctypes.byref(session)))
            if not session.value:
                raise _unavailable()
            raw = ctypes.cast(session, ctypes.c_char_p).value
            if raw is None or len(raw) > 64:
                raise _unavailable()
            identity = raw.decode("ascii")
            if not _SESSION_ID.fullmatch(identity):
                raise _unavailable()
            _check(self.library.sd_pidfd_get_owner_uid(pidfd, ctypes.byref(uid)))
            if uid.value == 0xFFFFFFFF:
                raise _unavailable()
            return identity, uid.value
        finally:
            if session.value:
                self.libc.free(session)

    def session(self, session_id: str) -> LinuxSessionObservation:
        if not _SESSION_ID.fullmatch(session_id):
            raise _unavailable()
        with _SessionBus(self.library) as bus:
            owner = bus.login_owner()
            with bus.call(_BUS_DESTINATION, _BUS_PATH, _BUS_DESTINATION, b"GetConnectionUnixUser", owner) as reply:
                if bus.read_integer(reply, b"u") != 0:
                    raise _unavailable()
                bus.require_end(reply)
            observation = bus.session_record(owner, session_id).desktop()
            if bus.login_owner() != owner or observation.session_id != session_id:
                raise _unavailable()
            bus.remaining_usec()
            return observation


class _SessionBus:
    """One exact native bus peer with a single aggregate call deadline."""

    def __init__(
        self, library: ctypes.CDLL, *, path: Path | None = None, peer_uid: int = 0, deadline: float | None = None
    ) -> None:
        self.library = library
        self.bus = ctypes.c_void_p()
        self.path = path or Path("/run/dbus/system_bus_socket")
        self.peer_uid = peer_uid
        self.deadline = deadline if deadline is not None else time.monotonic() + _BUS_TIMEOUT_SECONDS

    def remaining_usec(self) -> int:
        remaining = int((self.deadline - time.monotonic()) * 1_000_000)
        if remaining <= 0:
            raise _unavailable()
        return remaining

    def __enter__(self) -> _SessionBus:
        if sys.platform == "linux":
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                connection.settimeout(self.remaining_usec() / 1_000_000)
                connection.connect(str(self.path))
                credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                process_id, uid, _ = struct.unpack("3i", credentials)
                if process_id <= 0 or uid != self.peer_uid:
                    raise _unavailable()
                connection.setblocking(False)
                _check(self.library.sd_bus_new(ctypes.byref(self.bus)))
                if not self.bus.value:
                    raise _unavailable()
                _check(self.library.sd_bus_set_fd(self.bus, connection.fileno(), connection.fileno()))
                connection.detach()  # sd-bus now owns and closes this descriptor.
                _check(self.library.sd_bus_set_bus_client(self.bus, 1))
                _check(self.library.sd_bus_set_method_call_timeout(self.bus, self.remaining_usec()))
                _check(self.library.sd_bus_start(self.bus))
                # sd_bus_call's internal bus_ensure_running has an unbounded wait.
                # Complete authentication/Hello using our own deadline first.
                while True:
                    self.remaining_usec()
                    ready = self.library.sd_bus_is_ready(self.bus)
                    _check(ready)
                    if ready > 0:
                        break
                    processed = self.library.sd_bus_process(self.bus, None)
                    _check(processed)
                    if processed == 0:
                        _check(self.library.sd_bus_wait(self.bus, self.remaining_usec()))
                self.remaining_usec()
                return self
            except BaseException:
                self.close()
                raise
            finally:
                connection.close()
        raise _unavailable()

    def close(self) -> None:
        if self.bus.value:
            self.library.sd_bus_close_unref(self.bus)
            self.bus = ctypes.c_void_p()

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def call(
        self, destination: bytes, path: bytes, interface: bytes, method: bytes, argument: bytes | None = None
    ) -> Generator[ctypes.c_void_p]:
        request, reply = ctypes.c_void_p(), ctypes.c_void_p()
        try:
            _check(
                self.library.sd_bus_message_new_method_call(
                    self.bus, ctypes.byref(request), destination, path, interface, method
                )
            )
            if not request.value:
                raise _unavailable()
            _check(self.library.sd_bus_message_set_auto_start(request, 0))
            _check(self.library.sd_bus_message_set_allow_interactive_authorization(request, 0))
            if argument is not None:
                _check(self.library.sd_bus_message_append_basic(request, b"s", ctypes.c_char_p(argument)))
            _check(self.library.sd_bus_call(self.bus, request, self.remaining_usec(), None, ctypes.byref(reply)))
            if not reply.value:
                raise _unavailable()
            sender = self.library.sd_bus_message_get_sender(reply)
            if sender != destination:
                raise _unavailable()
            self.remaining_usec()
            yield reply
        finally:
            if reply.value:
                self.library.sd_bus_message_unref(reply)
            if request.value:
                self.library.sd_bus_message_unref(request)

    def login_owner(self) -> bytes:
        with self.call(_BUS_DESTINATION, _BUS_PATH, _BUS_DESTINATION, b"GetNameOwner", _LOGIN_DESTINATION) as reply:
            owner = self.read_string(reply, b"s", maximum=64)
            self.require_end(reply)
            if not _UNIQUE_OWNER.fullmatch(owner):
                raise _unavailable()
            return owner

    def read_string(self, reply: ctypes.c_void_p, kind: bytes, *, maximum: int = 128) -> bytes:
        value = ctypes.c_char_p()
        _check(self.library.sd_bus_message_read_basic(reply, kind, ctypes.byref(value)), required=True)
        raw = value.value
        if raw is None or len(raw) > maximum or b"\0" in raw:
            raise _unavailable()
        return raw

    def read_integer(self, reply: ctypes.c_void_p, kind: bytes) -> int:
        value = ctypes.c_uint64() if kind == b"t" else ctypes.c_uint32()
        _check(self.library.sd_bus_message_read_basic(reply, kind, ctypes.byref(value)), required=True)
        return value.value

    def require_end(self, reply: ctypes.c_void_p) -> None:
        _check(self.library.sd_bus_message_at_end(reply, 0), required=True)

    def sessions(self, owner: bytes) -> tuple[_SessionReference, ...]:
        with self.call(owner, _LOGIN_MANAGER, b"org.freedesktop.login1.Manager", b"ListSessions") as reply:
            return self.read_sessions(reply)

    def read_sessions(self, reply: ctypes.c_void_p) -> tuple[_SessionReference, ...]:
        rows: list[_SessionReference] = []
        seen: set[str] = set()
        seen_paths: set[bytes] = set()
        _check(self.library.sd_bus_message_enter_container(reply, b"a", b"(susso)"), required=True)
        while True:
            entry = self.library.sd_bus_message_enter_container(reply, b"r", b"susso")
            _check(entry)
            if entry == 0:
                break
            self.remaining_usec()
            if len(rows) >= _SESSION_LIMIT:
                raise _unavailable()
            identity = self.read_string(reply, b"s", maximum=64).decode("ascii")
            uid = self.read_integer(reply, b"u")
            # Account/seat labels are consumed and discarded, never retained.
            self.read_string(reply, b"s", maximum=256)
            self.read_string(reply, b"s", maximum=64)
            path = self.read_string(reply, b"o", maximum=240)
            self.require_end(reply)
            _check(self.library.sd_bus_message_exit_container(reply))
            row = _SessionReference(identity, uid, path)
            if identity in seen or path in seen_paths:
                raise _unavailable()
            seen.add(identity)
            seen_paths.add(path)
            rows.append(row)
        _check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        return tuple(sorted(rows, key=lambda row: (row.session_id, row.uid, row.object_path)))

    def session_record(self, owner: bytes, session_id: str, *, expected_path: bytes | None = None) -> _SessionRecord:
        with self.call(
            owner, _LOGIN_MANAGER, b"org.freedesktop.login1.Manager", b"GetSession", session_id.encode()
        ) as reply:
            path = self.read_string(reply, b"o", maximum=240)
            self.require_end(reply)
            if not _SESSION_PATH.fullmatch(path) or (expected_path is not None and path != expected_path):
                raise _unavailable()
        with self.call(owner, path, b"org.freedesktop.DBus.Properties", b"GetAll", _SESSION_INTERFACE) as reply:
            observation = self.read_session_record(reply)
        if observation.session_id != session_id:
            raise _unavailable()
        return observation

    def read_session_record(self, reply: ctypes.c_void_p) -> _SessionRecord:
        values: dict[str, str | int | bool] = {}
        seen: set[str] = set()
        _check(self.library.sd_bus_message_enter_container(reply, b"a", b"{sv}"), required=True)
        while True:
            entry = self.library.sd_bus_message_enter_container(reply, b"e", b"sv")
            _check(entry)
            if entry == 0:
                break
            self.remaining_usec()
            name = self.read_string(reply, b"s").decode("ascii")
            if name in seen or len(seen) >= 128:
                raise _unavailable()
            seen.add(name)
            signature = _PROPERTY_SIGNATURES.get(name)
            if signature is None:
                _check(self.library.sd_bus_message_skip(reply, b"v"), required=True)
            else:
                _check(self.library.sd_bus_message_enter_container(reply, b"v", signature), required=True)
                if signature == b"s":
                    values[name] = self.read_string(reply, b"s").decode("ascii")
                elif signature == b"(uo)":
                    _check(self.library.sd_bus_message_enter_container(reply, b"r", b"uo"), required=True)
                    values[name] = self.read_integer(reply, b"u")
                    user_path = self.read_string(reply, b"o")
                    if user_path != f"/org/freedesktop/login1/user/_{values[name]}".encode():
                        raise _unavailable()
                    self.require_end(reply)
                    _check(self.library.sd_bus_message_exit_container(reply))
                elif signature == b"b":
                    boolean = self.read_integer(reply, b"b")
                    if boolean not in (0, 1):
                        raise _unavailable()
                    values[name] = bool(boolean)
                else:
                    values[name] = self.read_integer(reply, b"t")
                self.require_end(reply)
                _check(self.library.sd_bus_message_exit_container(reply))
            self.require_end(reply)
            _check(self.library.sd_bus_message_exit_container(reply))
        _check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        if values.keys() != _PROPERTY_SIGNATURES.keys():
            raise _unavailable()
        session_id, uid, created = values["Id"], values["User"], values["TimestampMonotonic"]
        session_class, session_type, state = values["Class"], values["Type"], values["State"]
        locked = values["LockedHint"]
        if (
            not isinstance(session_id, str)
            or type(uid) is not int
            or type(created) is not int
            or not isinstance(session_class, str)
            or not isinstance(session_type, str)
            or not isinstance(state, str)
            or type(locked) is not bool
        ):
            raise _unavailable()
        return _SessionRecord(session_id, uid, created, session_class, session_type, state, locked)


@dataclass(frozen=True)
class LinuxLoginBinding:
    """Immutable native login incarnation; no originating process is retained."""

    os_owner_id: str
    boot_id: UUID
    session_id: str
    created_monotonic_usec: int
    gnome_lock: GnomeLockBinding | None = None

    @property
    def login_id(self) -> str:
        """Identify one boot, native session generation, and Unix owner."""
        return f"linux:{self.boot_id}:{self.session_id}:{self.created_monotonic_usec}:{self.os_owner_id}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Read this same login again, independently of the peer process lifetime."""
        return observe_linux_login(self, credential_facilities=credential_facilities)


def capture_linux_login(pidfd: int, *, expected_owner: str) -> LinuxLoginBinding:
    """Borrow a kernel-bound peer PIDFD and fence its session around the snapshot."""
    if sys.platform != "linux":
        raise _unavailable()
    try:
        _ensure_pidfd_alive(pidfd)
        native = _NativeLogin()
        boot = _boot_id()
        session_id, uid = native.peer_session(pidfd)
        if str(uid) != expected_owner:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        observation = native.session(session_id)
        if observation.uid != uid or observation.state not in ("online", "active"):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if native.peer_session(pidfd) != (session_id, uid) or _boot_id() != boot:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        _ensure_pidfd_alive(pidfd)
        lock_binding: GnomeLockBinding | None = None
        with suppress(RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
            lock_binding, _ = _gnome_observation(native, session_id, uid)
        if lock_binding is not None and (native.session(session_id) != observation or _boot_id() != boot):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        _ensure_pidfd_alive(pidfd)
        return LinuxLoginBinding(expected_owner, boot, session_id, observation.created_monotonic_usec, lock_binding)
    except (OSError, AttributeError, ValueError, TypeError, OverflowError):
        raise _unavailable() from None


def _gnome_observation(
    native: _NativeLogin,
    session_id: str,
    uid: int,
    expected: GnomeLockBinding | None = None,
    *,
    deadline: float | None = None,
) -> tuple[GnomeLockBinding, GnomeLockState]:
    deadline = deadline if deadline is not None else time.monotonic() + _BUS_TIMEOUT_SECONDS
    require_gnome_login_producer(uid)
    path = gnome_user_bus_path(uid)
    socket_identity = path.lstat()
    with _SessionBus(native.library, path=path, peer_uid=uid, deadline=deadline) as bus:
        result = sample_gnome_lock(
            bus, uid=uid, session_id=session_id, peer_session=native.peer_session, expected=expected
        )
        require_gnome_login_producer(uid)
        if gnome_user_bus_path(uid) != path or path.lstat() != socket_identity:
            raise _unavailable()
        bus.remaining_usec()
        return result


def observe_linux_login(binding: LinuxLoginBinding, *, credential_facilities: Availability) -> OsLoginContext:
    """Observe exact lifetime without promoting logind's lock hint to authority.

    Only the retained, same-owner GNOME observer can establish lock eligibility.
    Credential readiness remains independent of compositor integration.
    """
    try:
        boot_matches = _boot_id() == binding.boot_id
        native = _NativeLogin() if boot_matches else None
        observation = native.session(binding.session_id) if native is not None else None
        valid = (
            observation is not None
            and observation.session_id == binding.session_id
            and str(observation.uid) == binding.os_owner_id
            and observation.created_monotonic_usec == binding.created_monotonic_usec
            and observation.state in ("online", "active")
            and _boot_id() == binding.boot_id
        )
        locked = True
        eligibility = LoginEligibility.UNKNOWN if valid else LoginEligibility.INELIGIBLE
        if valid and native is not None and binding.gnome_lock is not None:
            try:
                _, lock_state = _gnome_observation(
                    native, binding.session_id, int(binding.os_owner_id), binding.gnome_lock
                )
                # Lock observations cannot outlive a changed native login snapshot.
                if native.session(binding.session_id) != observation or _boot_id() != binding.boot_id:
                    valid = False
                    eligibility = LoginEligibility.INELIGIBLE
                else:
                    locked = lock_state.safely_locked or lock_state.lock_generation > binding.gnome_lock.lock_generation
                    eligibility = lock_state.eligibility
            except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
                pass
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=valid,
            locked=locked,
            unattended=eligibility,
            credential_facilities=credential_facilities,
        )
    except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=False,
            locked=True,
            unattended=LoginEligibility.UNKNOWN,
            credential_facilities=credential_facilities,
        )


def linux_login_inventory(*, expected_owner: str) -> RuntimeLoginInventory:
    """Enumerate trusted owner desktops; incomplete absence never proves logout.

    One existing aggregate bus deadline covers enumeration and GNOME sampling.
    Local filesystem/native operations remain subject to their existing limits.
    The fixed per-user bus currently exposes only one GNOME Shell owner: other
    desktop rows remain uncertain unless that exact row's producer is verified.
    """
    unknown = RuntimeLoginInventory((), False)
    if sys.platform != "linux":
        return unknown
    try:
        uid = posix_owner_uid()
        if expected_owner != str(uid):
            return unknown
        deadline = time.monotonic() + _BUS_TIMEOUT_SECONDS
        boot = _boot_id()
        native = _NativeLogin()
        with _SessionBus(native.library, deadline=deadline) as bus:
            owner = bus.login_owner()
            with bus.call(_BUS_DESTINATION, _BUS_PATH, _BUS_DESTINATION, b"GetConnectionUnixUser", owner) as reply:
                if bus.read_integer(reply, b"u") != 0:
                    return unknown
                bus.require_end(reply)
            before = bus.sessions(owner)
            logins: list[LinuxLoginBinding] = []
            complete = True
            for row in before:
                bus.remaining_usec()
                if row.uid != uid:
                    continue
                try:
                    first = bus.session_record(owner, row.session_id, expected_path=row.object_path)
                    if first.uid != uid:
                        raise _unavailable()
                    if first.known_ineligible:
                        if bus.session_record(owner, row.session_id, expected_path=row.object_path) != first:
                            complete = False
                        continue
                    observation = first.desktop()
                    if observation.state not in ("online", "active"):
                        raise _unavailable()
                    lock_binding, state = _gnome_observation(native, row.session_id, uid, deadline=deadline)
                    if state.eligibility is not LoginEligibility.ELIGIBLE:
                        raise _unavailable()
                    if bus.session_record(owner, row.session_id, expected_path=row.object_path) != first:
                        raise _unavailable()
                    bus.remaining_usec()
                    logins.append(
                        LinuxLoginBinding(
                            expected_owner, boot, row.session_id, first.created_monotonic_usec, lock_binding
                        )
                    )
                except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
                    complete = False
            if bus.sessions(owner) != before or bus.login_owner() != owner or _boot_id() != boot:
                return unknown
            bus.remaining_usec()
            return RuntimeLoginInventory(tuple(logins), complete)
    except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        return unknown
