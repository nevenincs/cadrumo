"""Bounded, non-prompting custody in an existing GNOME Secret Service collection.

D-Bus sessions and sockets are closed on every path. SecretStorage and the
cryptographic library allocate immutable secret bytes; those copies cannot be
reliably wiped by Python and are retained only for the current operation.
"""

from __future__ import annotations

import os
import re
import secrets
import socket
import stat
import struct
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from .gnome_collection_protection import require_protected_gnome_collection

if TYPE_CHECKING:
    from jeepney import Parser

_SERVICE = "org.freedesktop.secrets"
_ROOT = "/org/freedesktop/secrets"
_SERVICE_IFACE = "org.freedesktop.Secret.Service"
_COLLECTION_IFACE = "org.freedesktop.Secret.Collection"
_ITEM_IFACE = "org.freedesktop.Secret.Item"
_SESSION_IFACE = "org.freedesktop.Secret.Session"
_PROPERTIES = "org.freedesktop.DBus.Properties"
_BUS = "org.freedesktop.DBus"
_BUS_PATH = "/org/freedesktop/DBus"
_ALGORITHM = "dh-ietf1024-sha256-aes128-cbc-pkcs7"
_CONTENT_TYPE = "application/octet-stream"
# GNOME returns text/plain for encrypted secret bytes regardless of the input MIME.
_GNOME_READ_CONTENT_TYPES = frozenset({_CONTENT_TYPE, "text/plain"})
_MAX_SECRET_SIZE = 2560
_MAX_REPLY_BYTES = 65536
_OPERATION_SECONDS = 5.0
_PATH_PATTERN = re.compile(r"/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\Z")


def _invalid() -> AutomationCustodyError:
    return AutomationCustodyError(AutomationCustodyCode.INVALID)


def _object_path(value: object, *, allow_root: bool = False) -> str:
    if allow_root and value == "/":
        return "/"
    if not isinstance(value, str) or len(value) > 1024 or not _PATH_PATTERN.fullmatch(value):
        raise _invalid()
    return value


def _body(value: object, length: int) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise _invalid()
    result = cast(tuple[Any, ...], value)
    if len(result) != length:
        raise _invalid()
    return result


def _attributes(namespace: str, account: str) -> dict[str, str]:
    if (
        not isinstance(namespace, str)
        or not isinstance(account, str)
        or not namespace.startswith("cadrumo.automation.")
        or len(namespace) <= len("cadrumo.automation.")
        or not account
        or len(namespace) + len(account) > 1024
        or any(ord(character) < 32 or ord(character) == 127 for character in namespace + account)
    ):
        raise _invalid()
    if sys.platform != "linux":
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    return {
        "application": "cadrumo",
        "namespace": namespace,
        "account": account,
        "xdg:schema": "org.freedesktop.Secret.Generic",
    }


def _user_bus_path() -> Path:
    """Select the kernel-owned user bus; ambient D-Bus addresses are not authority."""
    if sys.platform != "linux":
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    uid = os.getuid()
    directory = Path("/run/user") / str(uid)
    for parent in (Path("/run"), Path("/run/user")):
        observed = parent.lstat()
        if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != 0 or observed.st_mode & 0o022:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    observed = directory.lstat()
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != uid or stat.S_IMODE(observed.st_mode) != 0o700:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    path = directory / "bus"
    observed = path.lstat()
    if not stat.S_ISSOCK(observed.st_mode) or observed.st_uid != uid:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    return path


class _DeadlineBus:
    """Small synchronous D-Bus peer with one deadline including SASL and Hello."""

    deadline: float
    sock: socket.socket
    parser: Parser

    def __init__(self, path: Path, deadline: float) -> None:
        if sys.platform != "linux":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        from jeepney import Parser
        from jeepney.auth import Authenticator

        self.deadline = deadline
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.parser = Parser()
        self.serial = 0
        self.owner: str | None = None
        try:
            self.sock.settimeout(self.remaining())
            self.sock.connect(str(path))
            peer = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _, uid, _ = struct.unpack("3i", peer)
            if uid != os.getuid():
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            authenticator = Authenticator(enable_fds=False)
            for request in authenticator:
                self.sock.settimeout(self.remaining())
                self.sock.sendall(request)
                self.sock.settimeout(self.remaining())
                response = self.sock.recv(1024)
                if not response:
                    raise OSError
                authenticator.feed(response)
            self.sock.settimeout(self.remaining())
            self.sock.sendall(b"BEGIN\r\n")
            hello = self.call(_BUS_PATH, _BUS, "Hello", destination=_BUS)
            (name,) = _body(hello, 1)
            if not isinstance(name, str) or not name.startswith(":"):
                raise _invalid()
        except BaseException:
            self.close()
            raise

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return remaining

    def close(self) -> None:
        self.sock.close()

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
        from jeepney import DBusAddress, HeaderFields, MessageFlag, MessageType, new_method_call

        address = DBusAddress(path, bus_name=destination or self.owner or _SERVICE, interface=interface)
        message = new_method_call(address, method, signature, body)
        message.header.flags |= MessageFlag.no_auto_start
        self.serial += 1
        self.sock.settimeout(self.remaining())
        self.sock.sendall(message.serialise(serial=self.serial))
        received = 0
        while True:
            self.remaining()
            reply = self.parser.get_next_message()
            if reply is None:
                self.sock.settimeout(self.remaining())
                data = self.sock.recv(4096)
                if not data:
                    raise OSError
                received += len(data)
                if received > _MAX_REPLY_BYTES:
                    raise _invalid()
                self.parser.add_data(data)
                continue
            if reply.header.fields.get(HeaderFields.reply_serial) != self.serial:
                continue
            if reply.header.message_type is MessageType.error:
                error_name = reply.header.fields.get(HeaderFields.error_name)
                code = AutomationCustodyCode.UNAVAILABLE
                if error_name in {"org.freedesktop.Secret.Error.IsLocked", "org.freedesktop.DBus.Error.AccessDenied"}:
                    code = AutomationCustodyCode.NEEDS_USER
                elif error_name == "org.freedesktop.DBus.Error.NotSupported":
                    code = AutomationCustodyCode.UNSUPPORTED
                raise AutomationCustodyError(code)
            if reply.header.message_type is not MessageType.method_return:
                raise _invalid()
            if self.owner and destination is None and reply.header.fields.get(HeaderFields.sender) != self.owner:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if not isinstance(reply.body, tuple):
                raise _invalid()
            return reply.body

    def verify_owner(self) -> None:
        if sys.platform != "linux":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        (owner,) = _body(self.call(_BUS_PATH, _BUS, "GetNameOwner", "s", (_SERVICE,), destination=_BUS), 1)
        if not isinstance(owner, str) or not owner.startswith(":") or (self.owner and owner != self.owner):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        (uid,) = _body(self.call(_BUS_PATH, _BUS, "GetConnectionUnixUser", "s", (owner,), destination=_BUS), 1)
        if type(uid) is not int or uid != os.getuid():
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        (pid,) = _body(self.call(_BUS_PATH, _BUS, "GetConnectionUnixProcessID", "s", (owner,), destination=_BUS), 1)
        if type(pid) is not int or pid <= 0:
            raise _invalid()
        process = Path("/proc") / str(pid)
        if process.stat().st_uid != uid:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        executable = (process / "exe").resolve(strict=True)
        executable_status = executable.stat()
        if (
            executable.name != "gnome-keyring-daemon"
            or executable_status.st_uid != 0
            or executable_status.st_mode & 0o022
            or not stat.S_ISREG(executable_status.st_mode)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.owner = owner


@contextmanager
def _native_bus() -> Generator[_DeadlineBus]:
    try:
        bus = _DeadlineBus(_user_bus_path(), time.monotonic() + _OPERATION_SECONDS)
        try:
            bus.verify_owner()
            yield bus
            bus.verify_owner()
        finally:
            bus.close()
    except AutomationCustodyError:
        raise
    except (ValueError, TypeError, IndexError, KeyError, OverflowError):
        raise _invalid() from None
    except Exception:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None


def _property(bus: _DeadlineBus, path: str, interface: str, name: str, signature: str) -> Any:
    (variant,) = _body(bus.call(path, _PROPERTIES, "Get", "ss", (interface, name)), 1)
    actual_signature, value = _body(variant, 2)
    if actual_signature != signature:
        raise _invalid()
    return value


def _unlocked(bus: _DeadlineBus, path: str, interface: str) -> None:
    locked = _property(bus, path, interface, "Locked", "b")
    if type(locked) is not bool:
        raise _invalid()
    if locked:
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)


def _collection(bus: _DeadlineBus) -> str:
    (path,) = _body(bus.call(_ROOT, _SERVICE_IFACE, "ReadAlias", "s", ("default",)), 1)
    path = _object_path(path, allow_root=True)
    if path == "/":
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    if not path.startswith(_ROOT + "/collection/"):
        raise _invalid()
    _unlocked(bus, path, _COLLECTION_IFACE)
    return path


def _find(bus: _DeadlineBus, collection: str, attributes: dict[str, str]) -> str | None:
    _unlocked(bus, collection, _COLLECTION_IFACE)
    (paths,) = _body(bus.call(collection, _COLLECTION_IFACE, "SearchItems", "a{ss}", (attributes,)), 1)
    if not isinstance(paths, list):
        raise _invalid()
    matches = cast(list[object], paths)
    if len(matches) > 1:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if not matches:
        return None
    path = _object_path(matches[0])
    if not path.startswith(collection + "/"):
        raise _invalid()
    observed = _property(bus, path, _ITEM_IFACE, "Attributes", "a{ss}")
    if not isinstance(observed, dict) or observed != attributes:
        raise _invalid()
    _unlocked(bus, path, _ITEM_IFACE)
    return path


@contextmanager
def _session(bus: _DeadlineBus) -> Generator[Any]:
    from secretstorage.dhcrypto import DH_PRIME_1024, Session

    session = Session()
    try:
        public = session.my_public_key.to_bytes(128, "big")
        output, path = _body(bus.call(_ROOT, _SERVICE_IFACE, "OpenSession", "sv", (_ALGORITHM, ("ay", public))), 2)
        signature, value = _body(output, 2)
        if signature != "ay" or not isinstance(value, bytes) or not 1 <= len(value) <= 128:
            raise _invalid()
        server_key = int.from_bytes(value, "big")
        if not 1 < server_key < DH_PRIME_1024 - 1:
            raise _invalid()
        session.object_path = _object_path(path)
        if not session.object_path.startswith(_ROOT + "/session/"):
            raise _invalid()
        try:
            session.set_server_public_key(server_key)
            yield session
        finally:
            with suppress(Exception):
                bus.call(session.object_path, _SESSION_IFACE, "Close")
    finally:
        session.aes_key = None
        session.my_private_key = 0


def _read_item(bus: _DeadlineBus, path: str, session: Any) -> bytes:
    (secret,) = _body(bus.call(path, _ITEM_IFACE, "GetSecret", "o", (session.object_path,)), 1)
    session_path, iv, ciphertext, content_type = _body(secret, 4)
    if (
        session_path != session.object_path
        or not isinstance(iv, bytes)
        or len(iv) != 16
        or not isinstance(ciphertext, bytes)
        or not 0 < len(ciphertext) <= _MAX_SECRET_SIZE + 16
        or len(ciphertext) % 16
        or not isinstance(content_type, str)
        or content_type not in _GNOME_READ_CONTENT_TYPES
    ):
        raise _invalid()
    decryptor = Cipher(algorithms.AES(session.aes_key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    raw = unpadder.update(padded) + unpadder.finalize()
    if not 0 < len(raw) <= _MAX_SECRET_SIZE:
        raise _invalid()
    return raw


class LinuxSecretServiceAutomationSecretStore:
    """Explicit GNOME Secret Service backend with no unlock or prompt execution."""

    backend = NativeSecretBackend.LINUX_DBUS

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read the uniquely matching unlocked item within the existing collection."""
        attributes = _attributes(namespace, account)
        with _native_bus() as bus:
            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            path = _find(bus, collection, attributes)
            if path is None:
                return None
            with _session(bus) as session:
                return SecretBytes(_read_item(bus, path, session))

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Atomically replace exact attributes and verify the resulting secret."""
        attributes = _attributes(namespace, account)
        if not isinstance(value, SecretBytes):
            raise _invalid()
        raw = value.get_secret_value()
        if not 0 < len(raw) <= _MAX_SECRET_SIZE:
            raise _invalid()
        with _native_bus() as bus:
            from secretstorage.util import format_secret

            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            _find(bus, collection, attributes)
            with _session(bus) as session:
                properties = {
                    _ITEM_IFACE + ".Label": ("s", "Cadrumo automation"),
                    _ITEM_IFACE + ".Attributes": ("a{ss}", attributes),
                }
                item, prompt = _body(
                    bus.call(
                        collection,
                        _COLLECTION_IFACE,
                        "CreateItem",
                        "a{sv}(oayays)b",
                        (properties, format_secret(session, raw, _CONTENT_TYPE), True),
                    ),
                    2,
                )
                if _object_path(prompt, allow_root=True) != "/":
                    raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
                item = _object_path(item)
                observed = _find(bus, collection, attributes)
                if observed != item or not secrets.compare_digest(_read_item(bus, item, session), raw):
                    raise _invalid()

    def delete(self, namespace: str, account: str) -> None:
        """Delete the uniquely matching item and verify absence without prompting."""
        attributes = _attributes(namespace, account)
        with _native_bus() as bus:
            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            path = _find(bus, collection, attributes)
            if path is not None:
                (prompt,) = _body(bus.call(path, _ITEM_IFACE, "Delete"), 1)
                if _object_path(prompt, allow_root=True) != "/":
                    raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
            if _find(bus, collection, attributes) is not None:
                raise _invalid()
