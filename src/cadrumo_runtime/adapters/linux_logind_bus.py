"""Bounded logind system-bus protocol decoding."""

from __future__ import annotations

import ctypes
import re
import socket
import struct
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .linux_login_models import SESSION_PATH, SessionRecord, SessionReference, unavailable

_LOGIN_DESTINATION = b"org.freedesktop.login1"

_LOGIN_MANAGER = b"/org/freedesktop/login1"

_SESSION_INTERFACE = b"org.freedesktop.login1.Session"

BUS_DESTINATION = b"org.freedesktop.DBus"

BUS_PATH = b"/org/freedesktop/DBus"

BUS_TIMEOUT_SECONDS = 1.0

SESSION_LIMIT = 128

_UNIQUE_OWNER = re.compile(rb":[0-9]+\.[0-9]+\Z", re.ASCII)

_PROPERTY_SIGNATURES = {
    "Id": b"s",
    "User": b"(uo)",
    "TimestampMonotonic": b"t",
    "Class": b"s",
    "Type": b"s",
    "State": b"s",
    "LockedHint": b"b",
}


def check(result: int, *, required: bool = False) -> None:
    """Refuse as unavailable when an sd-bus result is negative, or zero where one is required."""
    if result < 0 or (required and result == 0):
        raise unavailable()


class SessionBus:
    """One exact native bus peer with a single aggregate call deadline."""

    def __init__(
        self, library: ctypes.CDLL, *, path: Path | None = None, peer_uid: int = 0, deadline: float | None = None
    ) -> None:
        """Bind the bus library, socket path, expected peer uid and overall call deadline."""
        self.library = library
        self.bus = ctypes.c_void_p()
        self.path = path or Path("/run/dbus/system_bus_socket")
        self.peer_uid = peer_uid
        self.deadline = deadline if deadline is not None else time.monotonic() + BUS_TIMEOUT_SECONDS

    def remaining_usec(self) -> int:
        """Return microseconds left before the deadline, refusing once it has passed."""
        remaining = int((self.deadline - time.monotonic()) * 1_000_000)
        if remaining <= 0:
            raise unavailable()
        return remaining

    def __enter__(self) -> SessionBus:
        """Connect to the system bus, verify the peer credentials and return the open bus."""
        if sys.platform == "linux":
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                connection.settimeout(self.remaining_usec() / 1_000_000)
                connection.connect(str(self.path))
                credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                process_id, uid, _ = struct.unpack("3i", credentials)
                if process_id <= 0 or uid != self.peer_uid:
                    raise unavailable()
                connection.setblocking(False)
                check(self.library.sd_bus_new(ctypes.byref(self.bus)))
                if not (self.bus.value is not None and self.bus.value):
                    raise unavailable()
                check(self.library.sd_bus_set_fd(self.bus, connection.fileno(), connection.fileno()))
                connection.detach()  # sd-bus now owns and closes this descriptor.
                check(self.library.sd_bus_set_bus_client(self.bus, 1))
                check(self.library.sd_bus_set_method_call_timeout(self.bus, self.remaining_usec()))
                check(self.library.sd_bus_start(self.bus))
                # sd_bus_call's internal bus_ensure_running has an unbounded wait.
                # Complete authentication/Hello using our own deadline first.
                while True:
                    self.remaining_usec()
                    ready = self.library.sd_bus_is_ready(self.bus)
                    check(ready)
                    if ready > 0:
                        break
                    processed = self.library.sd_bus_process(self.bus, None)
                    check(processed)
                    if processed == 0:
                        check(self.library.sd_bus_wait(self.bus, self.remaining_usec()))
                self.remaining_usec()
                return self
            except BaseException:
                self.close()
                raise
            finally:
                connection.close()
        raise unavailable()

    def close(self) -> None:
        """Close and release the bus handle if it is open."""
        if self.bus.value is not None and self.bus.value:
            self.library.sd_bus_close_unref(self.bus)
            self.bus = ctypes.c_void_p()

    def __exit__(self, *_: object) -> None:
        """Close the bus on leaving the context."""
        self.close()

    @contextmanager
    def call(
        self, destination: bytes, path: bytes, interface: bytes, method: bytes, argument: bytes | None = None
    ) -> Generator[ctypes.c_void_p]:
        """Call a bus method and yield its reply, releasing request and reply afterwards."""
        request, reply = ctypes.c_void_p(), ctypes.c_void_p()
        try:
            check(
                self.library.sd_bus_message_new_method_call(
                    self.bus, ctypes.byref(request), destination, path, interface, method
                )
            )
            if not (request.value is not None and request.value):
                raise unavailable()
            check(self.library.sd_bus_message_set_auto_start(request, 0))
            check(self.library.sd_bus_message_set_allow_interactive_authorization(request, 0))
            if argument is not None:
                check(self.library.sd_bus_message_append_basic(request, b"s", ctypes.c_char_p(argument)))
            check(self.library.sd_bus_call(self.bus, request, self.remaining_usec(), None, ctypes.byref(reply)))
            if not (reply.value is not None and reply.value):
                raise unavailable()
            sender = self.library.sd_bus_message_get_sender(reply)
            if sender != destination:
                raise unavailable()
            self.remaining_usec()
            yield reply
        finally:
            if reply.value:
                self.library.sd_bus_message_unref(reply)
            if request.value:
                self.library.sd_bus_message_unref(request)

    def login_owner(self) -> bytes:
        """Resolve the unique bus name that owns the login service."""
        with self.call(BUS_DESTINATION, BUS_PATH, BUS_DESTINATION, b"GetNameOwner", _LOGIN_DESTINATION) as reply:
            owner = self.read_string(reply, b"s", maximum=64)
            self.require_end(reply)
            if not _UNIQUE_OWNER.fullmatch(owner):
                raise unavailable()
            return owner

    def read_string(self, reply: ctypes.c_void_p, kind: bytes, *, maximum: int = 128) -> bytes:
        """Read a string from a reply, refusing null, oversize or NUL-containing text."""
        value = ctypes.c_char_p()
        check(self.library.sd_bus_message_read_basic(reply, kind, ctypes.byref(value)), required=True)
        raw = value.value
        if raw is None or len(raw) > maximum or b"\0" in raw:
            raise unavailable()
        return raw

    def read_integer(self, reply: ctypes.c_void_p, kind: bytes) -> int:
        """Read an unsigned integer of the given basic kind from a reply."""
        value = ctypes.c_uint64() if kind == b"t" else ctypes.c_uint32()
        check(self.library.sd_bus_message_read_basic(reply, kind, ctypes.byref(value)), required=True)
        return value.value

    def require_end(self, reply: ctypes.c_void_p) -> None:
        """Require that the reply message holds no further content."""
        check(self.library.sd_bus_message_at_end(reply, 0), required=True)

    def sessions(self, owner: bytes) -> tuple[SessionReference, ...]:
        """List the login sessions known to the login service owner."""
        with self.call(owner, _LOGIN_MANAGER, b"org.freedesktop.login1.Manager", b"ListSessions") as reply:
            return self.read_sessions(reply)

    def read_sessions(self, reply: ctypes.c_void_p) -> tuple[SessionReference, ...]:
        """Read the session array of a ListSessions reply, refusing duplicate ids or paths."""
        rows: list[SessionReference] = []
        seen: set[str] = set()
        seen_paths: set[bytes] = set()
        check(self.library.sd_bus_message_enter_container(reply, b"a", b"(susso)"), required=True)
        while True:
            entry = self.library.sd_bus_message_enter_container(reply, b"r", b"susso")
            check(entry)
            if entry == 0:
                break
            self.remaining_usec()
            if len(rows) >= SESSION_LIMIT:
                raise unavailable()
            identity = self.read_string(reply, b"s", maximum=64).decode("ascii")
            uid = self.read_integer(reply, b"u")
            # Account/seat labels are consumed and discarded, never retained.
            self.read_string(reply, b"s", maximum=256)
            self.read_string(reply, b"s", maximum=64)
            path = self.read_string(reply, b"o", maximum=240)
            self.require_end(reply)
            check(self.library.sd_bus_message_exit_container(reply))
            row = SessionReference(identity, uid, path)
            if identity in seen or path in seen_paths:
                raise unavailable()
            seen.add(identity)
            seen_paths.add(path)
            rows.append(row)
        check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        return tuple(sorted(rows, key=lambda row: (row.session_id, row.uid, row.object_path)))

    def session_record(self, owner: bytes, session_id: str, *, expected_path: bytes | None = None) -> SessionRecord:
        """Fetch and validate one login session record by id, optionally matching its path."""
        with self.call(
            owner, _LOGIN_MANAGER, b"org.freedesktop.login1.Manager", b"GetSession", session_id.encode()
        ) as reply:
            path = self.read_string(reply, b"o", maximum=240)
            self.require_end(reply)
            if not SESSION_PATH.fullmatch(path) or (expected_path is not None and path != expected_path):
                raise unavailable()
        with self.call(owner, path, b"org.freedesktop.DBus.Properties", b"GetAll", _SESSION_INTERFACE) as reply:
            observation = self.read_session_record(reply)
        if observation.session_id != session_id:
            raise unavailable()
        return observation

    def read_session_record(self, reply: ctypes.c_void_p) -> SessionRecord:
        """Read a session's properties from a reply and build its validated record."""
        values = self._read_session_properties(reply)
        return self._build_session_record(values)

    def _read_session_properties(self, reply: ctypes.c_void_p) -> dict[str, str | int | bool]:
        values: dict[str, str | int | bool] = {}
        seen: set[str] = set()
        check(self.library.sd_bus_message_enter_container(reply, b"a", b"{sv}"), required=True)
        while True:
            entry = self.library.sd_bus_message_enter_container(reply, b"e", b"sv")
            check(entry)
            if entry == 0:
                break
            self.remaining_usec()
            self._read_session_property(reply, values, seen)
        check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        return values

    def _read_session_property(
        self,
        reply: ctypes.c_void_p,
        values: dict[str, str | int | bool],
        seen: set[str],
    ) -> None:
        name = self.read_string(reply, b"s").decode("ascii")
        if name in seen or len(seen) >= 128:
            raise unavailable()
        seen.add(name)
        signature = _PROPERTY_SIGNATURES.get(name)
        if signature is None:
            check(self.library.sd_bus_message_skip(reply, b"v"), required=True)
        else:
            check(self.library.sd_bus_message_enter_container(reply, b"v", signature), required=True)
            values[name] = self._read_session_property_value(reply, name, signature)
            self.require_end(reply)
            check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        check(self.library.sd_bus_message_exit_container(reply))

    def _read_session_property_value(self, reply: ctypes.c_void_p, name: str, signature: bytes) -> str | int | bool:
        if signature == b"s":
            return self.read_string(reply, b"s").decode("ascii")
        if signature == b"(uo)":
            check(self.library.sd_bus_message_enter_container(reply, b"r", b"uo"), required=True)
            uid = self.read_integer(reply, b"u")
            user_path = self.read_string(reply, b"o")
            if user_path != f"/org/freedesktop/login1/user/_{uid}".encode():
                raise unavailable()
            self.require_end(reply)
            check(self.library.sd_bus_message_exit_container(reply))
            return uid
        if signature == b"b":
            boolean = self.read_integer(reply, b"b")
            if boolean not in (0, 1):
                raise unavailable()
            return bool(boolean)
        return self.read_integer(reply, b"t")

    def _build_session_record(self, values: dict[str, str | int | bool]) -> SessionRecord:
        if values.keys() != _PROPERTY_SIGNATURES.keys():
            raise unavailable()
        session_id, uid, created = values["Id"], values["User"], values["TimestampMonotonic"]
        session_class, session_type, state = values["Class"], values["Type"], values["State"]
        locked = values["LockedHint"]
        if not isinstance(session_id, str):
            raise unavailable()
        if type(uid) is not int:
            raise unavailable()
        if type(created) is not int:
            raise unavailable()
        if not isinstance(session_class, str):
            raise unavailable()
        if not isinstance(session_type, str):
            raise unavailable()
        if not isinstance(state, str):
            raise unavailable()
        if type(locked) is not bool:
            raise unavailable()
        return SessionRecord(session_id, uid, created, session_class, session_type, state, locked)
