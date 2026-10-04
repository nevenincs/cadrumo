"""Read-only GNOME lock observations bound to a native desktop incarnation.

Only the explicitly provisioned producer is supported. A Shell outside the
caller's native logind session is unavailable, including user-manager launches
for which sd_pidfd_get_session supplies no session. Observations are snapshots,
not an atomic promise that a later operating-system lock cannot occur.
"""

from __future__ import annotations

import ctypes
import os
import re
import select
import stat
import sys
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import LoginEligibility
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_path
from .linux_pidfd import open_linux_pidfd

GNOME_LOGIN_EXTENSION_UUID = "login-observation@cadrumo.org"
GNOME_LOGIN_BUS_NAME = b"org.cadrumo.Runtime.LoginObservation1"
GNOME_LOGIN_OBJECT_PATH = b"/org/cadrumo/Runtime/LoginObservation1"
_SHELL = b"org.gnome.Shell"
_SHIELD = b"org.gnome.Shell.ScreenShield"
_BUS = b"org.freedesktop.DBus"
_BUS_PATH = b"/org/freedesktop/DBus"
_OWNER = re.compile(rb":[0-9]+\.[0-9]+\Z", re.ASCII)
_BUS_ID = re.compile(rb"[0-9a-f]{32}\Z", re.ASCII)


def _unavailable() -> RuntimeRefusalError:
    return RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


class GnomeObservationBus(Protocol):
    """Borrowed bounded native bus; callers own its connection and deadline."""

    def call(
        self, destination: bytes, path: bytes, interface: bytes, method: bytes, argument: bytes | None = None
    ) -> AbstractContextManager[ctypes.c_void_p]:
        """Issue one non-activating, non-interactive call to the exact owner."""
        ...

    def read_string(self, reply: ctypes.c_void_p, kind: bytes, *, maximum: int = 128) -> bytes:
        """Read one bounded scalar without accepting a variant or extra values."""
        ...

    def read_integer(self, reply: ctypes.c_void_p, kind: bytes) -> int:
        """Read one exactly typed native integer or boolean."""
        ...

    def require_end(self, reply: ctypes.c_void_p) -> None:
        """Reject trailing protocol values."""
        ...


@dataclass(frozen=True)
class GnomeLockState:
    """Strict closed producer snapshot, without producer-supplied login labels."""

    epoch: UUID
    sequence: int
    locked: bool
    active: bool
    mode: str
    lock_generation: int = 0

    @property
    def eligibility(self) -> LoginEligibility:
        """Accept only complete unlocked or complete locked desktop states."""
        if (self.mode == "user" and not self.locked and not self.active) or (
            self.mode == "unlock-dialog" and self.locked and self.active
        ):
            return LoginEligibility.ELIGIBLE
        return LoginEligibility.UNKNOWN

    @property
    def safely_locked(self) -> bool:
        """An incomplete transition never releases an unlocked observation."""
        return self.locked or self.active or self.eligibility is LoginEligibility.UNKNOWN


@dataclass(frozen=True)
class GnomeLockBinding:
    """One bus, Shell process and enabled producer incarnation."""

    bus_id: bytes
    owner: bytes
    pid: int
    epoch: UUID
    lock_generation: int = 0


def read_gnome_lock_state(bus: GnomeObservationBus, owner: bytes) -> GnomeLockState:
    """Decode the supported V1 response; missing fields and new versions refuse."""
    with bus.call(owner, GNOME_LOGIN_OBJECT_PATH, GNOME_LOGIN_BUS_NAME, b"GetState") as reply:
        version = bus.read_integer(reply, b"u")
        epoch_text = bus.read_string(reply, b"s", maximum=36).decode("ascii")
        sequence = bus.read_integer(reply, b"u")
    lock_generation = bus.read_integer(reply, b"u")
    locked = bus.read_integer(reply, b"b")
    active = bus.read_integer(reply, b"b")
    mode = bus.read_string(reply, b"s", maximum=32).decode("ascii")
    bus.require_end(reply)
    epoch = UUID(epoch_text)
    if not _valid_lock_version(version, epoch, epoch_text):
        raise _unavailable()
    if not _valid_lock_counters(sequence, lock_generation):
        raise _unavailable()
    if not _valid_lock_bits(locked, active) or mode not in ("user", "unlock-dialog"):
        raise _unavailable()
    return GnomeLockState(epoch, sequence, bool(locked), bool(active), mode, lock_generation)


def _valid_lock_version(version: int, epoch: UUID, epoch_text: str) -> bool:
    return type(version) is int and version == 1 and str(epoch) == epoch_text and epoch.int != 0


def _valid_lock_counters(sequence: int, generation: int) -> bool:
    return (
        type(sequence) is int
        and 0 < sequence <= 0xFFFFFFFF
        and type(generation) is int
        and 0 <= generation <= 0xFFFFFFFF
    )


def _valid_lock_bits(locked: int, active: int) -> bool:
    return type(locked) is int and locked in (0, 1) and type(active) is int and active in (0, 1)


def _owner(bus: GnomeObservationBus, name: bytes) -> bytes:
    with bus.call(_BUS, _BUS_PATH, _BUS, b"GetNameOwner", name) as reply:
        value = bus.read_string(reply, b"s", maximum=64)
        bus.require_end(reply)
    if not _OWNER.fullmatch(value):
        raise _unavailable()
    return value


def _bus_integer(bus: GnomeObservationBus, method: bytes, owner: bytes) -> int:
    with bus.call(_BUS, _BUS_PATH, _BUS, method, owner) as reply:
        value = bus.read_integer(reply, b"u")
        bus.require_end(reply)
        return value


def _bus_id(bus: GnomeObservationBus) -> bytes:
    with bus.call(_BUS, _BUS_PATH, _BUS, b"GetId") as reply:
        value = bus.read_string(reply, b"s", maximum=32)
        bus.require_end(reply)
    if not _BUS_ID.fullmatch(value):
        raise _unavailable()
    return value


def _identity(bus: GnomeObservationBus, uid: int) -> tuple[bytes, bytes, int]:
    identity = _bus_id(bus)
    owner = _owner(bus, GNOME_LOGIN_BUS_NAME)
    if _owner(bus, _SHELL) != owner or _owner(bus, _SHIELD) != owner:
        raise _unavailable()
    if _bus_integer(bus, b"GetConnectionUnixUser", owner) != uid:
        raise _unavailable()
    pid = _bus_integer(bus, b"GetConnectionUnixProcessID", owner)
    if pid <= 0:
        raise _unavailable()
    return identity, owner, pid


def _alive(pidfd: int) -> None:
    if sys.platform != "linux":
        raise _unavailable()
    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    if os.get_inheritable(pidfd) or poller.poll(0):
        raise _unavailable()


def sample_gnome_lock(
    bus: GnomeObservationBus,
    *,
    uid: int,
    session_id: str,
    peer_session: Callable[[int], tuple[str, int]],
    expected: GnomeLockBinding | None = None,
) -> tuple[GnomeLockBinding, GnomeLockState]:
    """Bracket fresh state with exact bus owners and a borrowed native PIDFD."""
    if sys.platform != "linux" or uid != os.getuid():
        raise _unavailable()
    identity, owner, pid = _identity(bus, uid)
    with _shell_pidfd(pid, uid) as pidfd:
        _alive(pidfd)
        if peer_session(pidfd) != (session_id, uid):
            raise _unavailable()
        state = read_gnome_lock_state(bus, owner)
        binding = GnomeLockBinding(identity, owner, pid, state.epoch, state.lock_generation)
        if expected is not None:
            if (identity, owner, pid, state.epoch) != (
                expected.bus_id,
                expected.owner,
                expected.pid,
                expected.epoch,
            ) or state.lock_generation < expected.lock_generation:
                raise _unavailable()
            binding = expected
        if _identity(bus, uid) != (identity, owner, pid) or peer_session(pidfd) != (session_id, uid):
            raise _unavailable()
        _alive(pidfd)
        return binding, state


@contextmanager
def _shell_pidfd(pid: int, uid: int) -> Generator[int]:
    if sys.platform != "linux":
        raise _unavailable()
    pidfd = open_linux_pidfd(pid)
    try:
        process = Path("/proc") / str(pid)
        if process.stat().st_uid != uid:
            raise _unavailable()
        executable = (process / "exe").resolve(strict=True)
        if executable not in (Path("/usr/bin/gnome-shell"), Path("/usr/libexec/gnome-shell")):
            raise _unavailable()
        observed = _require_protected_gnome_shell(executable)
        _alive(pidfd)
        yield pidfd
        _alive(pidfd)
        if (process / "exe").resolve(strict=True) != executable or _file_identity(executable.stat()) != _file_identity(
            observed
        ):
            raise _unavailable()
    finally:
        os.close(pidfd)


def _require_protected_gnome_shell(executable: Path) -> os.stat_result:
    observed = executable.stat()
    for parent in executable.parents:
        ancestor = parent.lstat()
        if not stat.S_ISDIR(ancestor.st_mode) or ancestor.st_uid != 0 or ancestor.st_mode & 0o022:
            raise _unavailable()
    if not stat.S_ISREG(observed.st_mode) or observed.st_uid != 0 or observed.st_mode & 0o022:
        raise _unavailable()
    return observed


def gnome_user_bus_path(uid: int) -> Path:
    """Select only the native owner-only user runtime directory and bus socket."""
    if sys.platform != "linux" or uid != os.getuid():
        raise _unavailable()
    for path in (Path("/run"), Path("/run/user")):
        _require_root_runtime_directory(path)
    directory = Path("/run/user") / str(uid)
    _require_user_runtime_directory(directory, uid)
    path = directory / "bus"
    _require_user_bus_socket(path, uid)
    return path


def _require_root_runtime_directory(path: Path) -> None:
    observed = path.lstat()
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != 0 or observed.st_mode & 0o022:
        raise _unavailable()


def _require_user_runtime_directory(path: Path, uid: int) -> None:
    observed = path.lstat()
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != uid or stat.S_IMODE(observed.st_mode) != 0o700:
        raise _unavailable()


def _require_user_bus_socket(path: Path, uid: int) -> None:
    observed = path.lstat()
    if not stat.S_ISSOCK(observed.st_mode) or observed.st_uid != uid:
        raise _unavailable()


def require_gnome_login_producer(uid: int) -> None:
    """Verify exact installed resources in the configured private extension."""
    if sys.platform != "linux" or uid != os.getuid():
        raise _unavailable()
    extensions_root = storage_path(StorageCategory.GNOME_EXTENSIONS)
    if not extensions_root.is_absolute() or ".." in extensions_root.parts:
        raise _unavailable()
    components = (*extensions_root.parts[1:], GNOME_LOGIN_EXTENSION_UUID)
    directory = _open_producer_directory(components, uid)
    try:
        _require_producer_files(directory, uid)
    finally:
        os.close(directory)


def _open_producer_directory(components: tuple[str, ...], uid: int) -> int:
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for index, component in enumerate(components):
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            os.close(directory)
            directory = child
            _require_producer_directory(directory, uid, final=index == len(components) - 1)
        return directory
    except BaseException:
        os.close(directory)
        raise


def _require_producer_directory(directory: int, uid: int, *, final: bool) -> None:
    observed = os.fstat(directory)
    if observed.st_uid not in (0, uid) or observed.st_mode & 0o022:
        raise _unavailable()
    if final and (observed.st_uid != uid or stat.S_IMODE(observed.st_mode) != 0o700):
        raise _unavailable()


def _require_producer_files(directory: int, uid: int) -> None:
    for name in ("extension.js", "metadata.json"):
        _require_producer_file(directory, name, uid)


def _require_producer_file(directory: int, name: str, uid: int) -> None:
    descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != uid
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
            or not 0 < observed.st_size <= 65536
        ):
            raise _unavailable()
        with os.fdopen(os.dup(descriptor), "rb") as source:
            actual = source.read(65537)
        reference = files("cadrumo").joinpath("_data/local_runtime/gnome_login", name).read_bytes()
        after = os.fstat(descriptor)
        if actual != reference or _file_identity(after) != _file_identity(observed):
            raise _unavailable()
    finally:
        os.close(descriptor)


def _file_identity(observed: os.stat_result) -> tuple[int, ...]:
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_size,
        observed.st_mode,
        observed.st_uid,
        observed.st_gid,
        observed.st_nlink,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )
