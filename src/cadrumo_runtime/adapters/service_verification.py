"""Installed image admission anchored in retained native connection evidence."""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from cadrumo.core.diagnostic_log import diagnostic_slow_call
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.logging import get_logger
from cadrumo.core.path_confinement import HostPathRefusal, opened_confined_file
from cadrumo.core.storage_environment import storage_mode
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor, VerifiedServicePeer
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.windows_channel import WindowsChannel

from .boot_record import runtime_package_directory
from .macos_login import macos_peer_audit_token
from .macos_process import read_macos_process
from .native_peer import require_live_native_peer
from .service_descriptors import package_member_path

_log = get_logger(__name__)

_SERVICE_RECHECK_SLOW_SECONDS: Final = 1.0
"""Reading a peer's process and image from the kernel can stall; a recheck this long is reported."""
_MAXIMUM_PACKAGE_MANIFEST_BYTES = 16 * 1024 * 1024
_MAXIMUM_SERVICE_DESCRIPTOR_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class NativeProcessIdentity:
    """Identify a process incarnation by id, parent, birth marker, and image."""

    pid: int
    parent_pid: int
    born: int
    image: str


def _windows_process_identity(pid: int, owner: str) -> NativeProcessIdentity:
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.UNAVAILABLE)
    from ctypes import wintypes

    from cadrumo_client.transport.windows_native_io import windows_image_path, windows_owner_sid

    class BasicInformation(ctypes.Structure):
        _fields_ = (
            ("reserved", ctypes.c_void_p),
            ("peb", ctypes.c_void_p),
            ("reserved2", ctypes.c_void_p * 2),
            ("pid", ctypes.c_size_t),
            ("parent", ctypes.c_size_t),
        )

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    opened = kernel.OpenProcess
    opened.argtypes, opened.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
    handle = opened(0x1000 | 0x100000, False, pid)
    if not handle:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    close = kernel.CloseHandle
    close.argtypes, close.restype = (wintypes.HANDLE,), wintypes.BOOL
    try:
        if windows_owner_sid(handle) != owner:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        wait = kernel.WaitForSingleObject
        wait.argtypes, wait.restype = (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD
        if wait(handle, 0) != 258:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        times = kernel.GetProcessTimes
        pointer = ctypes.POINTER(wintypes.FILETIME)
        times.argtypes, times.restype = (wintypes.HANDLE, pointer, pointer, pointer, pointer), wintypes.BOOL
        created, exited, cpu, user = (wintypes.FILETIME() for _ in range(4))
        if not times(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(cpu), ctypes.byref(user)):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        native = ctypes.WinDLL("ntdll")
        query = native.NtQueryInformationProcess
        query.argtypes = (wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p)
        query.restype = wintypes.LONG
        info = BasicInformation()
        if query(handle, 0, ctypes.byref(info), ctypes.sizeof(info), None) != 0:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return NativeProcessIdentity(
            pid, int(info.parent), created.dwHighDateTime << 32 | created.dwLowDateTime, str(windows_image_path(handle))
        )
    finally:
        close(handle)


def native_process_identity(pid: int, owner: str) -> NativeProcessIdentity:
    """Read current kernel image, parent and creation identity; unknown facts refuse."""
    if sys.platform == "linux":
        directory = Path("/proc") / str(pid)
        if str(directory.stat().st_uid) != owner:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        fields = (directory / "stat").read_text(encoding="ascii").rsplit(") ", 1)[1].split()
        return NativeProcessIdentity(pid, int(fields[1]), int(fields[19]), os.readlink(directory / "exe"))
    if sys.platform == "darwin":
        observed = read_macos_process(pid, expected_owner=owner)
        native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = native.proc_pidpath
        query.argtypes, query.restype = (ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        if query(pid, buffer, len(buffer)) <= 0:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return NativeProcessIdentity(
            pid,
            observed.parent_pid,
            observed.started_seconds * 1_000_000 + observed.started_microseconds,
            os.fsdecode(buffer.value),
        )
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.UNAVAILABLE)
    return _windows_process_identity(pid, owner)


_MAXIMUM_COMMAND_LINE_BYTES = 2 * 32768 + 64


def _windows_process_arguments(pid: int, owner: str) -> tuple[str, ...]:
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.UNAVAILABLE)
    from ctypes import wintypes

    from cadrumo_client.transport.windows_native_io import windows_owner_sid

    class UnicodeString(ctypes.Structure):
        _fields_ = (("length", wintypes.USHORT), ("maximum", wintypes.USHORT), ("buffer", ctypes.c_void_p))

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    opened = kernel.OpenProcess
    opened.argtypes, opened.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
    handle = opened(0x1000, False, pid)
    if not handle:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    close = kernel.CloseHandle
    close.argtypes, close.restype = (wintypes.HANDLE,), wintypes.BOOL
    try:
        if windows_owner_sid(handle) != owner:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        query = ctypes.WinDLL("ntdll").NtQueryInformationProcess
        query.argtypes = (wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p)
        query.restype = wintypes.LONG
        needed = wintypes.ULONG()
        query(handle, 60, None, 0, ctypes.byref(needed))
        if not 0 < needed.value <= _MAXIMUM_COMMAND_LINE_BYTES:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        buffer = ctypes.create_string_buffer(needed.value)
        if query(handle, 60, buffer, needed.value, ctypes.byref(needed)) != 0:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        text = UnicodeString.from_buffer(buffer)
        line = ctypes.wstring_at(text.buffer, text.length // 2) if text.buffer else ""
    finally:
        close(handle)
    split = ctypes.WinDLL("shell32", use_last_error=True).CommandLineToArgvW
    split.argtypes, split.restype = (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)), ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    arguments = split(line, ctypes.byref(count))
    if not arguments:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    free = kernel.LocalFree
    free.argtypes, free.restype = (ctypes.c_void_p,), ctypes.c_void_p
    try:
        return tuple(str(arguments[index]) for index in range(1, count.value))
    finally:
        free(ctypes.cast(arguments, ctypes.c_void_p))


def native_process_arguments(pid: int, owner: str) -> tuple[str, ...]:
    """Read the arguments a process was started with, after its image; unknown facts refuse."""
    if sys.platform == "linux":
        directory = Path("/proc") / str(pid)
        if str(directory.stat().st_uid) != owner:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        parts = (directory / "cmdline").read_bytes().split(b"\0")
        return tuple(os.fsdecode(part) for part in parts[1:-1])
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.UNAVAILABLE)
    return _windows_process_arguments(pid, owner)


def _require_channel(channel: ByteChannel, identity: NativeProcessIdentity) -> None:
    if isinstance(channel, (WindowsChannel, PosixChannel)):
        require_live_native_peer(channel)
    else:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    image_path = channel.peer.image_path
    if image_path is None and isinstance(channel, PosixChannel) and sys.platform == "darwin":
        with channel.pinned_peer_socket() as sock:
            image_path = macos_peer_audit_token(sock, expected_owner=channel.peer.os_owner_id).image_path
    if (
        channel.peer.process_id != identity.pid
        or image_path is None
        or Path(image_path).resolve() != Path(identity.image).resolve()
    ):
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)


def _file_identity(status: os.stat_result) -> str:
    return f"{status.st_dev}:{status.st_ino}:{status.st_size}:{status.st_mtime_ns}"


def _running_image_identity(identity: NativeProcessIdentity) -> str:
    """Identify the file the process executes now; Linux names it even after replacement or exec."""
    if sys.platform == "linux":
        return _file_identity(os.stat(Path("/proc") / str(identity.pid) / "exe"))
    return _file_identity(Path(identity.image).stat())


def _verified_service_image(
    identity: NativeProcessIdentity, descriptor: InstalledServiceDescriptor
) -> tuple[Path, str, str] | None:
    candidate = Path(identity.image)
    if any(is_link_like(part) for part in (candidate, *candidate.parents)):
        return None
    image = candidate.resolve(strict=True)
    if image != Path(descriptor.launch_image).resolve(strict=True):
        return None
    with opened_confined_file(candidate, max_bytes=128 * 1024 * 1024) as opened:
        if isinstance(opened, HostPathRefusal):
            return None
        payload = opened.read_bytes()
        if isinstance(payload, HostPathRefusal):
            return None
        digest = sha256_hex(payload)
        image_identity = _file_identity(opened.status())
    if digest != descriptor.image_digest or _running_image_identity(identity) != image_identity:
        return None
    return image, digest, image_identity


def _installed_parent_path(package: str, image_path: str, descriptor_path: str) -> tuple[Path, Path] | None:
    root = Path(package)
    if any(is_link_like(part) for part in (root, *root.parents)):
        return None
    root = root.resolve(strict=True)
    observed = Path(image_path)
    expected = Path(descriptor_path)
    if any(is_link_like(part) for part in (observed, *observed.parents, expected, *expected.parents)):
        return None
    resolved_observed = observed.resolve(strict=True)
    resolved_expected = expected.resolve(strict=True)
    if resolved_observed != resolved_expected or not resolved_expected.is_relative_to(root):
        return None
    member = package_member_path(root, resolved_expected.relative_to(root).as_posix())
    if member is None or member[1] != resolved_expected:
        return None
    return root, resolved_expected


def _descendant_chain(child: NativeProcessIdentity, service_peer: VerifiedServicePeer, owner: str) -> bool:
    chain = [child]
    for _ in range(64):
        if child.pid == service_peer.process_id:
            if str(child.born) != service_peer.process_incarnation or child.image != service_peer.image_path:
                return False
            return all(native_process_identity(item.pid, owner) == item for item in chain)
        parent = native_process_identity(child.parent_pid, owner)
        if parent.born > child.born or parent.pid in {item.pid for item in chain}:
            return False
        chain.append(parent)
        child = parent
    return False


class InstalledNativeServiceVerifier:
    """Match dedicated package images and rechecked kernel ancestry."""

    def verify_service(
        self, context: ConnectionContext, channel: ByteChannel, descriptor: InstalledServiceDescriptor
    ) -> VerifiedServicePeer | None:
        """Match the retained connection peer to the installed service descriptor."""
        try:
            if context.peer != channel.peer or context.peer.process_id is None:
                return None
            identity = native_process_identity(context.peer.process_id, context.peer.os_owner_id)
            _require_channel(channel, identity)
            verified_image = _verified_service_image(identity, descriptor)
            if verified_image is None:
                return None
            image, digest, image_identity = verified_image
            expected = descriptor.launch_arguments
            if expected:
                started = native_process_arguments(identity.pid, context.peer.os_owner_id)
                if started[: len(expected)] != expected:
                    return None
            if native_process_identity(identity.pid, context.peer.os_owner_id) != identity:
                return None
            _require_channel(channel, identity)
            return VerifiedServicePeer(
                descriptor.service_id,
                descriptor.descriptor_digest,
                identity.pid,
                str(identity.born),
                str(image),
                digest,
                context.connection_id,
                context.runtime_boot_id,
                image_identity,
            )
        except (RefusalError, OSError, ValueError, IndexError):
            return None

    def recheck_service(self, context: ConnectionContext, channel: ByteChannel, peer: VerifiedServicePeer) -> bool:
        """Prove a later request comes from the incarnation admitted, without hashing the image again.

        A process keeps executing the image it was verified against: the same
        kernel incarnation on the same retained channel, still running the same
        image file, is the evidence ``verify_service`` established.
        """
        with diagnostic_slow_call(_log, "service_recheck_slow", threshold_seconds=_SERVICE_RECHECK_SLOW_SECONDS):
            try:
                if (
                    context.peer != channel.peer
                    or context.peer.process_id != peer.process_id
                    or context.connection_id != peer.connection_id
                    or context.runtime_boot_id != peer.runtime_boot_id
                ):
                    return False
                identity = native_process_identity(peer.process_id, context.peer.os_owner_id)
                if (
                    str(identity.born) != peer.process_incarnation
                    or str(Path(identity.image).resolve(strict=True)) != peer.image_path
                    or _running_image_identity(identity) != peer.image_identity
                ):
                    return False
                _require_channel(channel, identity)
                return True
            except (RefusalError, OSError, ValueError, IndexError):
                return False

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        """Verify a desktop parent against its exact bounded package image."""
        try:
            package = runtime_package_directory(Path(sys.executable), mode=storage_mode().mode)
            if package is None:
                return False
            resolved_expected = _installed_parent_path(package, image_path, descriptor_path)
            if resolved_expected is None:
                return False
            root, expected_image = resolved_expected
            with opened_confined_file(expected_image, max_bytes=128 * 1024 * 1024, root=root) as opened:
                if isinstance(opened, HostPathRefusal):
                    return False
                payload = opened.read_bytes()
            if isinstance(payload, HostPathRefusal):
                return False
            return sha256_hex(payload) == image_digest
        except Exception:
            return False

    def verify_descendant(
        self, context: ConnectionContext, channel: ByteChannel, service_peer: VerifiedServicePeer, group_id: UUID
    ) -> bool:
        """Check process ancestry and incarnation evidence for the retained service peer."""
        # The group id routes to the retained service connection. Kernel ancestry
        # and process incarnation identify a descendant; the supervisor owns Job
        # and process-tree containment evidence.
        if group_id != service_peer.connection_id or context.peer.process_id is None:
            return False
        try:
            child = native_process_identity(context.peer.process_id, context.peer.os_owner_id)
            _require_channel(channel, child)
            return _descendant_chain(child, service_peer, context.peer.os_owner_id)
        except (RefusalError, OSError, ValueError, IndexError):
            return False
