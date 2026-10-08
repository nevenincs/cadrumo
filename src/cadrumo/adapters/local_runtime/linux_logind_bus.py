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

from .linux_login_models import _SESSION_PATH, _SessionRecord, _SessionReference, _unavailable

_LOGIN_DESTINATION = b"org.freedesktop.login1"

_LOGIN_MANAGER = b"/org/freedesktop/login1"

_SESSION_INTERFACE = b"org.freedesktop.login1.Session"

_BUS_DESTINATION = b"org.freedesktop.DBus"

_BUS_PATH = b"/org/freedesktop/DBus"

_BUS_TIMEOUT_SECONDS = 1.0

_SESSION_LIMIT = 128

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


def _check(result: int, *, required: bool = False) -> None:
    if result < 0 or (required and result == 0):
        raise _unavailable()


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
        values = self._read_session_properties(reply)
        return self._build_session_record(values)

    def _read_session_properties(self, reply: ctypes.c_void_p) -> dict[str, str | int | bool]:
        values: dict[str, str | int | bool] = {}
        seen: set[str] = set()
        _check(self.library.sd_bus_message_enter_container(reply, b"a", b"{sv}"), required=True)
        while True:
            entry = self.library.sd_bus_message_enter_container(reply, b"e", b"sv")
            _check(entry)
            if entry == 0:
                break
            self.remaining_usec()
            self._read_session_property(reply, values, seen)
        _check(self.library.sd_bus_message_exit_container(reply))
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
            raise _unavailable()
        seen.add(name)
        signature = _PROPERTY_SIGNATURES.get(name)
        if signature is None:
            _check(self.library.sd_bus_message_skip(reply, b"v"), required=True)
        else:
            _check(self.library.sd_bus_message_enter_container(reply, b"v", signature), required=True)
            values[name] = self._read_session_property_value(reply, name, signature)
            self.require_end(reply)
            _check(self.library.sd_bus_message_exit_container(reply))
        self.require_end(reply)
        _check(self.library.sd_bus_message_exit_container(reply))

    def _read_session_property_value(self, reply: ctypes.c_void_p, name: str, signature: bytes) -> str | int | bool:
        if signature == b"s":
            return self.read_string(reply, b"s").decode("ascii")
        if signature == b"(uo)":
            _check(self.library.sd_bus_message_enter_container(reply, b"r", b"uo"), required=True)
            uid = self.read_integer(reply, b"u")
            user_path = self.read_string(reply, b"o")
            if user_path != f"/org/freedesktop/login1/user/_{uid}".encode():
                raise _unavailable()
            self.require_end(reply)
            _check(self.library.sd_bus_message_exit_container(reply))
            return uid
        if signature == b"b":
            boolean = self.read_integer(reply, b"b")
            if boolean not in (0, 1):
                raise _unavailable()
            return bool(boolean)
        return self.read_integer(reply, b"t")

    def _build_session_record(self, values: dict[str, str | int | bool]) -> _SessionRecord:
        if values.keys() != _PROPERTY_SIGNATURES.keys():
            raise _unavailable()
        session_id, uid, created = values["Id"], values["User"], values["TimestampMonotonic"]
        session_class, session_type, state = values["Class"], values["Type"], values["State"]
        locked = values["LockedHint"]
        if not isinstance(session_id, str):
            raise _unavailable()
        if type(uid) is not int:
            raise _unavailable()
        if type(created) is not int:
            raise _unavailable()
        if not isinstance(session_class, str):
            raise _unavailable()
        if not isinstance(session_type, str):
            raise _unavailable()
        if not isinstance(state, str):
            raise _unavailable()
        if type(locked) is not bool:
            raise _unavailable()
        return _SessionRecord(session_id, uid, created, session_class, session_type, state, locked)
