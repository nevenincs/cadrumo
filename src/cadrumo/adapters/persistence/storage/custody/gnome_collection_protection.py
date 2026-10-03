"""Bounded GNOME V1 metadata attestation for a selected persistent collection.

TRUSTED proves an observed nonempty master, not password strength. Independent
metadata and Secret Service calls cannot atomically exclude password changes.
No login, prompt, secret value, keyring file or object mutation is used here.
Wire contracts: GNOME 50.0 pkcs11/rpc-layer/gkm-rpc-private.h and
daemon/dbus/gkd-secret-util.c; unsupported capability fails closed.
"""

from __future__ import annotations

import os
import socket
import stat
import struct
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Protocol, cast

from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

_MAX_FRAME = 65536
_MAX_SLOTS = 8
_BASE = 0x80000000 | 0x474E4D45
_COLLECTION_CLASS = _BASE + 110
_CLASS, _TOKEN, _TRUSTED, _ID = 0, 1, 0x86, 0x102
_TRANSIENT, _LOCKED = _BASE + 201, _BASE + 210
_PREFIX = "/org/freedesktop/secrets/collection/"
_BUS = "org.freedesktop.DBus"
_HANDSHAKE = b"PRIVATE-GNOME-KEYRING-PKCS11-PROTOCOL-V-1"
_CALLS = {
    "C_Initialize": (1, b"ay", b""),
    "C_Finalize": (2, b"", b""),
    "C_GetSlotList": (4, b"yfu", b"au"),
    "C_GetTokenInfo": (6, b"u", b"ssssuuuuuuuuuuuvvs"),
    "C_OpenSession": (11, b"uu", b"u"),
    "C_CloseSession": (12, b"u", b""),
    "C_GetAttributeValue": (27, b"uufA", b"aAu"),
    "C_FindObjectsInit": (29, b"uaA", b""),
    "C_FindObjects": (30, b"ufu", b"au"),
    "C_FindObjectsFinal": (31, b"u", b""),
}


class GnomeCollectionBusProtocol(Protocol):
    """Existing authenticated bus and its unchanged absolute operation deadline."""

    deadline: float
    owner: str | None

    def verify_owner(self) -> None:
        """Verify the selected GNOME process, executable and unique owner."""
        ...

    def call(
        self,
        path: str,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple[Any, ...] = (),
        *,
        destination: str | None = None,
    ) -> tuple[Any, ...]:
        """Perform one bounded call to the pinned owner or native bus."""
        ...


class _MetadataSocketProtocol(Protocol):
    def settimeout(self, value: float | None, /) -> None: ...

    def connect(self, address: str, /) -> None: ...

    def getsockopt(self, level: int, option: int, length: int, /) -> bytes: ...

    def sendall(self, data: bytes, /) -> None: ...

    def recv(self, length: int, /) -> bytes: ...

    def close(self) -> None: ...


def _require(condition: bool, code: AutomationCustodyCode = AutomationCustodyCode.INVALID) -> None:
    if not condition:
        raise AutomationCustodyError(code)


def _one(body: tuple[Any, ...]) -> Any:
    _require(isinstance(body, tuple) and len(body) == 1)
    return body[0]


def _boolean_variant(value: object) -> bool:
    if not isinstance(value, tuple):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    parts = cast(tuple[object, ...], value)
    if len(parts) != 2 or parts[0] != "b":
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    locked = parts[1]
    if type(locked) is not bool:
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    return locked


@contextmanager
def _close_on_exit(close: Callable[[], None]) -> Generator[None]:
    """Require successful cleanup on success; preserve a primary refusal."""
    try:
        yield
    except BaseException:
        with suppress(Exception):
            close()
        raise
    else:
        close()


def gnome_collection_id(collection: str) -> bytes:
    """Decode only canonical GNOME collection paths, with an exact roundtrip."""
    _require(isinstance(collection, str) and collection.startswith(_PREFIX) and len(collection) <= 1024)
    encoded = collection[len(_PREFIX) :]
    result = bytearray()
    index = 0
    while index < len(encoded):
        character = encoded[index]
        if character.isascii() and character.isalnum():
            result.append(ord(character))
            index += 1
        else:
            _require(character == "_" and index + 2 < len(encoded))
            hexadecimal = encoded[index + 1 : index + 3]
            _require(all(value in "0123456789abcdef" for value in hexadecimal))
            result.append(int(hexadecimal, 16))
            index += 3
    _require(bool(result) and 0 not in result)
    roundtrip = "".join(
        chr(value) if chr(value).isascii() and chr(value).isalnum() else f"_{value:02x}" for value in result
    )
    _require(roundtrip == encoded)
    return bytes(result)


def _u32(value: int) -> bytes:
    return struct.pack(">I", value)


def _ulong(value: int) -> bytes:
    return struct.pack(">Q", value)


def _blob(value: bytes) -> bytes:
    return _u32(len(value)) + value


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.offset = data, 0

    def take(self, length: int) -> bytes:
        _require(0 <= length <= len(self.data) - self.offset)
        value = self.data[self.offset : self.offset + length]
        self.offset += length
        return value

    def number(self, size: int = 4) -> int:
        return int.from_bytes(self.take(size), "big")

    def blob(self, maximum: int = _MAX_FRAME) -> bytes:
        length = self.number()
        _require(length <= maximum)
        return self.take(length)

    def handles(self, maximum: int) -> tuple[int, ...]:
        _require(self.take(1) == b"\x01")
        count = self.number()
        _require(count <= maximum)
        result = tuple(self.number(8) for _ in range(count))
        _require(all(result) and len(set(result)) == len(result))
        self.finish()
        return result

    def finish(self) -> None:
        _require(self.offset == len(self.data))


def _control_directory(control: object) -> tuple[Path, int]:
    """Pin the owner-only directory without traversing any symlink component."""
    _require(
        isinstance(control, str) and 0 < len(control) <= 1024 and "\0" not in control,
        AutomationCustodyCode.UNAVAILABLE,
    )
    path = Path(str(control))
    _require(path.is_absolute() and str(path) == control and ".." not in path.parts, AutomationCustodyCode.UNAVAILABLE)
    uid = os.getuid()
    for parent in reversed(path.parents):
        info = parent.lstat()
        _require(
            stat.S_ISDIR(info.st_mode) and info.st_uid in (0, uid) and not info.st_mode & 0o022,
            AutomationCustodyCode.UNAVAILABLE,
        )
    info = path.lstat()
    _require(
        stat.S_ISDIR(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o700,
        AutomationCustodyCode.UNAVAILABLE,
    )
    descriptor = os.open(path, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        pinned = os.fstat(descriptor)
        _require(
            (pinned.st_dev, pinned.st_ino, pinned.st_uid, pinned.st_mode)
            == (info.st_dev, info.st_ino, info.st_uid, info.st_mode),
            AutomationCustodyCode.UNAVAILABLE,
        )
        return path, descriptor
    except BaseException:
        os.close(descriptor)
        raise


class _MetadataRpc:
    """Closed read-only V1 subset; each frame shares the existing deadline."""

    def __init__(self, directory_fd: int, *, provider_pid: int, deadline: float) -> None:
        self.deadline = deadline
        self.sock: _MetadataSocketProtocol = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            observed = os.stat("pkcs11", dir_fd=directory_fd, follow_symlinks=False)
            _require(
                stat.S_ISSOCK(observed.st_mode) and observed.st_uid == os.getuid() and not observed.st_mode & 0o077,
                AutomationCustodyCode.UNAVAILABLE,
            )
            self.sock.settimeout(self.remaining())
            # The pinned directory descriptor avoids re-traversing its pathname.
            self.sock.connect(f"/proc/self/fd/{directory_fd}/pkcs11")
            pid, uid, _gid = struct.unpack("3i", self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            _require(pid == provider_pid and uid == os.getuid(), AutomationCustodyCode.UNAVAILABLE)
            after = os.stat("pkcs11", dir_fd=directory_fd, follow_symlinks=False)
            _require(
                (observed.st_dev, observed.st_ino, observed.st_uid, observed.st_mode)
                == (after.st_dev, after.st_ino, after.st_uid, after.st_mode),
                AutomationCustodyCode.UNAVAILABLE,
            )
            self.sock.settimeout(self.remaining())
            self.sock.sendall(b"\0")  # Native credentials prefix, not a password.
        except BaseException:
            self.close()
            raise

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        _require(remaining > 0, AutomationCustodyCode.UNAVAILABLE)
        return remaining

    def receive(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            self.sock.settimeout(self.remaining())
            chunk = self.sock.recv(length - len(data))
            _require(bool(chunk), AutomationCustodyCode.UNAVAILABLE)
            data.extend(chunk)
        return bytes(data)

    def call(self, name: str, payload: bytes = b"") -> _Reader:
        _require(name in _CALLS)
        call_id, signature, response = _CALLS[name]
        data = _u32(call_id) + _blob(signature) + payload
        _require(len(data) <= _MAX_FRAME)
        self.sock.settimeout(self.remaining())
        self.sock.sendall(_u32(len(data)) + data)
        length = int.from_bytes(self.receive(4), "big")
        _require(4 <= length <= _MAX_FRAME)
        reply = _Reader(self.receive(length))
        returned_id = reply.number()
        if returned_id == 0:
            native_code = reply.number(8)
            reply.finish()
            _require(native_code > 0)
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        _require(returned_id == call_id and reply.blob(32) == response)
        return reply

    def empty(self, name: str, payload: bytes = b"") -> None:
        self.call(name, payload).finish()

    def close(self) -> None:
        self.sock.close()


def _secret_slot(rpc: _MetadataRpc) -> int:
    slots = rpc.call("C_GetSlotList", b"\x01" + _u32(_MAX_SLOTS)).handles(_MAX_SLOTS)
    matches: list[int] = []
    for slot in slots:
        reply = rpc.call("C_GetTokenInfo", _ulong(slot))
        label, manufacturer, model, serial = (reply.blob(32) for _ in range(4))
        _require(tuple(map(len, (label, manufacturer, model, serial))) == (32, 32, 16, 16))
        for _ in range(11):
            reply.number(8)
        reply.take(4)
        _require(len(reply.blob(16)) == 16)
        reply.finish()
        if label.rstrip(b" ") == b"Secret Store" and serial.rstrip(b" ") == b"1:SECRET:MAIN":
            _require(manufacturer.rstrip(b" ") == b"Gnome Keyring", AutomationCustodyCode.UNAVAILABLE)
            matches.append(slot)
    _require(len(matches) == 1, AutomationCustodyCode.UNAVAILABLE)
    return matches[0]


def _collection_metadata(rpc: _MetadataRpc, session: int, identifier: bytes) -> dict[int, bytes]:
    template = ((_CLASS, struct.pack("@L", _COLLECTION_CLASS)), (_ID, identifier))
    encoded = _u32(len(template)) + b"".join(
        _u32(kind) + b"\x01" + _u32(len(value)) + _blob(value) for kind, value in template
    )
    rpc.empty("C_FindObjectsInit", _ulong(session) + encoded)
    try:
        matches = rpc.call("C_FindObjects", _ulong(session) + _u32(2)).handles(2)
    finally:
        rpc.empty("C_FindObjectsFinal", _ulong(session))
    _require(len(matches) == 1, AutomationCustodyCode.UNAVAILABLE)
    requested = (
        (_CLASS, 8),
        (_ID, len(identifier)),
        (_TOKEN, 1),
        (_TRANSIENT, 1),
        (_TRUSTED, 1),
        (_LOCKED, 1),
    )
    payload = _ulong(session) + _ulong(matches[0]) + _u32(len(requested))
    payload += b"".join(_u32(kind) + _u32(length) for kind, length in requested)
    reply = rpc.call("C_GetAttributeValue", payload)
    _require(reply.number() == len(requested))
    values: dict[int, bytes] = {}
    invalid_attribute = False
    for expected_kind, expected_length in requested:
        _require(reply.number() == expected_kind)
        valid = reply.take(1)
        _require(valid in (b"\0", b"\x01"))
        if valid == b"\0":
            invalid_attribute = True
            continue
        length = reply.number()
        value = reply.blob(1024)
        _require(length == expected_length and len(value) == expected_length)
        values[expected_kind] = value
    native_code = reply.number(8)
    reply.finish()
    _require(not native_code and not invalid_attribute, AutomationCustodyCode.UNAVAILABLE)
    _require(values[_CLASS] == struct.pack("@L", _COLLECTION_CLASS) and values[_ID] == identifier)
    for kind in (_TOKEN, _TRANSIENT, _TRUSTED, _LOCKED):
        _require(values[kind] in (b"\0", b"\x01"))
    return values


def _read_metadata(rpc: _MetadataRpc, identifier: bytes) -> dict[int, bytes]:
    rpc.empty("C_Initialize", b"\x01" + _blob(_HANDSHAKE))
    with _close_on_exit(lambda: rpc.empty("C_Finalize")):
        opened = rpc.call("C_OpenSession", _ulong(_secret_slot(rpc)) + _ulong(4))
        session = opened.number(8)
        opened.finish()
        _require(session > 0)
        # These scopes own only this connection's new session. Every cleanup
        # call retains the original absolute operation deadline.
        with _close_on_exit(lambda: rpc.empty("C_CloseSession", _ulong(session))):
            return _collection_metadata(rpc, session, identifier)


def require_protected_gnome_collection(bus: GnomeCollectionBusProtocol, collection: str) -> None:
    """Refuse before item access unless exact native suitability is observed."""
    try:
        _require(sys.platform == "linux" and struct.calcsize("@L") == 8, AutomationCustodyCode.UNAVAILABLE)
        identifier = gnome_collection_id(collection)
        bus.verify_owner()
        owner = bus.owner
        _require(isinstance(owner, str) and owner.startswith(":"), AutomationCustodyCode.UNAVAILABLE)
        gnome_owner = _one(
            bus.call("/org/freedesktop/DBus", _BUS, "GetNameOwner", "s", ("org.gnome.keyring",), destination=_BUS)
        )
        _require(gnome_owner == owner, AutomationCustodyCode.UNAVAILABLE)
        pid = _one(
            bus.call("/org/freedesktop/DBus", _BUS, "GetConnectionUnixProcessID", "s", (owner,), destination=_BUS)
        )
        _require(type(pid) is int and pid > 0, AutomationCustodyCode.UNAVAILABLE)
        control = _one(bus.call("/org/gnome/keyring/daemon", "org.gnome.keyring.Daemon", "GetControlDirectory"))
        _directory, directory_fd = _control_directory(control)
        with _close_on_exit(lambda: os.close(directory_fd)):
            rpc = _MetadataRpc(directory_fd, provider_pid=pid, deadline=bus.deadline)
            with _close_on_exit(rpc.close):
                values = _read_metadata(rpc, identifier)
        bus.verify_owner()
        _require(bus.owner == owner, AutomationCustodyCode.UNAVAILABLE)
        gnome_owner = _one(
            bus.call("/org/freedesktop/DBus", _BUS, "GetNameOwner", "s", ("org.gnome.keyring",), destination=_BUS)
        )
        _require(gnome_owner == owner, AutomationCustodyCode.UNAVAILABLE)
        alias = _one(
            bus.call("/org/freedesktop/secrets", "org.freedesktop.Secret.Service", "ReadAlias", "s", ("default",))
        )
        _require(alias == collection, AutomationCustodyCode.UNAVAILABLE)
        locked = _boolean_variant(
            _one(
                bus.call(
                    collection,
                    "org.freedesktop.DBus.Properties",
                    "Get",
                    "ss",
                    ("org.freedesktop.Secret.Collection", "Locked"),
                )
            )
        )
        _require(values[_TOKEN] == b"\x01" and values[_TRANSIENT] == b"\0", AutomationCustodyCode.UNAVAILABLE)
        _require(
            not locked and values[_LOCKED] == b"\0" and values[_TRUSTED] == b"\x01", AutomationCustodyCode.NEEDS_USER
        )
    except AutomationCustodyError as error:
        if error.reason is AutomationCustodyCode.UNSUPPORTED:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        raise
    except (ValueError, TypeError, IndexError, KeyError, OverflowError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
    except Exception:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
