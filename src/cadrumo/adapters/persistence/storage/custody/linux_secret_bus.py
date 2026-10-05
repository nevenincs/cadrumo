"""Deadline-bound user D-Bus transport with a verified GNOME service owner."""

from __future__ import annotations

import os
import socket
import stat
import struct
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from .linux_secret_cleanup import close_secret_bus_after_failure
from .linux_secret_contracts import BUS, BUS_PATH, MAX_REPLY_BYTES, SERVICE, invalid_secret_reply, secret_reply_body

if TYPE_CHECKING:
    from jeepney import Message, Parser


def user_secret_bus_path() -> Path:
    """Select the kernel-owned user bus; ambient D-Bus addresses are not authority."""
    if sys.platform != "linux":
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    uid = os.getuid()
    directory = Path("/run/user") / str(uid)
    for parent in (Path("/run"), Path("/run/user")):
        observed = parent.lstat()
        _require_system_bus_parent(observed)
    observed = directory.lstat()
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != uid or stat.S_IMODE(observed.st_mode) != 0o700:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    path = directory / "bus"
    observed = path.lstat()
    if not stat.S_ISSOCK(observed.st_mode) or observed.st_uid != uid:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    return path


class DeadlineSecretBus:
    """Small synchronous D-Bus peer with one deadline including SASL and Hello."""

    deadline: float
    serial: int
    owner: str | None
    sock: socket.socket
    parser: Parser

    def __init__(self, path: Path, deadline: float) -> None:
        """Own one socket through peer admission, SASL, and bus Hello."""
        if sys.platform != "linux":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        from jeepney import Parser
        from jeepney.auth import Authenticator

        self.deadline = deadline
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.parser = Parser()
            self.serial = 0
            self.owner = None
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
            hello = self.call(BUS_PATH, BUS, "Hello", destination=BUS)
            (name,) = secret_reply_body(hello, 1)
            if not isinstance(name, str) or not name.startswith(":"):
                raise invalid_secret_reply()
        except BaseException as error:
            close_secret_bus_after_failure(self, error)
            raise

    def remaining(self) -> float:
        """Return the unspent part of the original operation deadline."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return remaining

    def close(self) -> None:
        """Disconnect the owned native D-Bus socket."""
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
        """Send a request without auto-start and admit only its bounded reply."""
        from jeepney import DBusAddress, HeaderFields, MessageFlag, new_method_call

        address = DBusAddress(path, bus_name=destination or self.owner or SERVICE, interface=interface)
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
                received = self._receive_reply_bytes(received)
                continue
            if reply.header.fields.get(HeaderFields.reply_serial) != self.serial:
                continue
            return self._admit_reply(reply, destination)

    def _receive_reply_bytes(self, received: int) -> int:
        """Account for every received byte before admitting more parser input."""
        self.sock.settimeout(self.remaining())
        data = self.sock.recv(4096)
        if not data:
            raise OSError
        received += len(data)
        if received > MAX_REPLY_BYTES:
            raise invalid_secret_reply()
        self.parser.add_data(data)
        return received

    def _admit_reply(self, reply: Message, destination: str | None) -> tuple[Any, ...]:
        """Require a typed reply from the pinned service after serial matching."""
        from jeepney import HeaderFields, MessageType

        if reply.header.message_type is MessageType.error:
            error_name = reply.header.fields.get(HeaderFields.error_name)
            code = AutomationCustodyCode.UNAVAILABLE
            if error_name in {"org.freedesktop.Secret.Error.IsLocked", "org.freedesktop.DBus.Error.AccessDenied"}:
                code = AutomationCustodyCode.NEEDS_USER
            elif error_name == "org.freedesktop.DBus.Error.NotSupported":
                code = AutomationCustodyCode.UNSUPPORTED
            raise AutomationCustodyError(code)
        if reply.header.message_type is not MessageType.method_return:
            raise invalid_secret_reply()
        if self.owner and destination is None and reply.header.fields.get(HeaderFields.sender) != self.owner:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if not isinstance(reply.body, tuple):
            raise invalid_secret_reply()
        return reply.body

    def verify_owner(self) -> None:
        """Pin the service to the same native user and protected GNOME executable."""
        if sys.platform != "linux":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        (owner,) = secret_reply_body(self.call(BUS_PATH, BUS, "GetNameOwner", "s", (SERVICE,), destination=BUS), 1)
        if not isinstance(owner, str) or not owner.startswith(":") or (self.owner and owner != self.owner):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        (uid,) = secret_reply_body(self.call(BUS_PATH, BUS, "GetConnectionUnixUser", "s", (owner,), destination=BUS), 1)
        if type(uid) is not int or uid != os.getuid():
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        (pid,) = secret_reply_body(
            self.call(BUS_PATH, BUS, "GetConnectionUnixProcessID", "s", (owner,), destination=BUS), 1
        )
        if type(pid) is not int or pid <= 0:
            raise invalid_secret_reply()
        _require_gnome_process_owner(pid, uid)
        self.owner = owner


def _require_system_bus_parent(observed: os.stat_result) -> None:
    """Require protected root-owned native parents of the user bus directory."""
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != 0 or observed.st_mode & 0o022:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)


def _require_gnome_process_owner(pid: int, uid: int) -> None:
    """Admit the protected GNOME keyring executable for the same native user."""
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
