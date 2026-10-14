"""Installed image admission anchored in retained native connection evidence."""

from __future__ import annotations

import ctypes
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from cadrumo.core.link_safety import is_link_like
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

_MAXIMUM_PACKAGE_MANIFEST_BYTES = 16 * 1024 * 1024
_MAXIMUM_SERVICE_DESCRIPTOR_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class NativeProcessIdentity:
    """Identify a process incarnation by id, parent, birth marker, and image."""

    pid: int
    parent_pid: int
    born: int
    image: str


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
            if digest != descriptor.image_digest:
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
            )
        except (RefusalError, OSError, ValueError, IndexError):
            return None

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        """Verify a desktop parent against its exact bounded package image."""
        try:
            package = runtime_package_directory(Path(sys.executable), mode=storage_mode().mode)
            if package is None:
                return False
            root = Path(package)
            if any(is_link_like(part) for part in (root, *root.parents)):
                return False
            root = root.resolve(strict=True)
            observed = Path(image_path)
            expected = Path(descriptor_path)
            if any(is_link_like(part) for part in (observed, *observed.parents, expected, *expected.parents)):
                return False
            resolved_observed = observed.resolve(strict=True)
            resolved_expected = expected.resolve(strict=True)
            if resolved_observed != resolved_expected or not resolved_expected.is_relative_to(root):
                return False
            member = _package_member_path(root, resolved_expected.relative_to(root).as_posix())
            if member is None or member[1] != resolved_expected:
                return False
            with opened_confined_file(resolved_expected, max_bytes=128 * 1024 * 1024, root=root) as opened:
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
            chain = [child]
            for _ in range(64):
                if child.pid == service_peer.process_id:
                    if str(child.born) != service_peer.process_incarnation or child.image != service_peer.image_path:
                        return False
                    return all(native_process_identity(item.pid, context.peer.os_owner_id) == item for item in chain)
                parent = native_process_identity(child.parent_pid, context.peer.os_owner_id)
                if parent.born > child.born or parent.pid in {item.pid for item in chain}:
                    return False
                chain.append(parent)
                child = parent
            return False
        except (RefusalError, OSError, ValueError, IndexError):
            return False


def installed_service_descriptors() -> tuple[InstalledServiceDescriptor, ...]:
    """Load package-owned capabilities, with image identity fixed by package inventory."""
    package = runtime_package_directory(Path(sys.executable), mode=storage_mode().mode)
    if package is None:
        return ()
    root = Path(package)
    if any(is_link_like(part) for part in (root, *root.parents)):
        return ()
    try:
        root = root.resolve(strict=True)
    except OSError:
        return ()
    path = root / "data" / "service-descriptors.json"
    try:
        manifest_raw = _read_package_member(
            root / "data" / "package-manifest.json", root=root, maximum_bytes=_MAXIMUM_PACKAGE_MANIFEST_BYTES
        )
        raw = _read_package_member(path, root=root, maximum_bytes=_MAXIMUM_SERVICE_DESCRIPTOR_BYTES)
        manifest = json.loads(
            manifest_raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if type(manifest) is not dict or type(manifest.get("files")) is not dict:
            return ()
        files = manifest["files"]
        expected = files.get("data/service-descriptors.json")
        if type(expected) is not str or sha256_hex(raw) != expected:
            return ()
        documents = json.loads(
            raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if type(documents) is not list:
            return ()
        descriptors: list[InstalledServiceDescriptor] = []
        service_ids: set[str] = set()
        for item in documents:
            if type(item) is not dict:
                return ()
            document = dict(item)
            digest_document = {key: value for key, value in document.items() if key != "descriptor_digest"}
            if sha256_hex(canonical_json_bytes(digest_document)) != document["descriptor_digest"]:
                return ()
            service_id = document["service_id"]
            if type(service_id) is not str or service_id in service_ids:
                return ()
            service_ids.add(service_id)
            if type(document.get("record_capabilities")) is not list:
                return ()
            capabilities = []
            for record in document["record_capabilities"]:
                if type(record) is not dict or type(record.get("capability")) is not str:
                    return ()
                capabilities.append(record["capability"])
            if len(capabilities) != len(set(capabilities)):
                return ()
            launch_image = _package_member_path(root, document.get("launch_image"))
            if launch_image is None:
                return ()
            _image, resolved_image = launch_image
            if files.get(document["launch_image"]) != document["image_digest"]:
                return ()
            document["launch_image"] = str(resolved_image)
            parents = document.get("allowed_parent_images", [])
            if type(parents) is not list:
                return ()
            for parent in parents:
                if type(parent) is not dict:
                    return ()
                parent_path = _package_member_path(root, parent.get("launch_image"))
                if parent_path is None:
                    return ()
                _parent_image, resolved_parent = parent_path
                if files.get(parent.get("launch_image")) != parent.get("image_digest"):
                    return ()
                parent["launch_image"] = str(resolved_parent)
            descriptors.append(InstalledServiceDescriptor.model_validate_json(canonical_json_bytes(document)))
        return tuple(descriptors)
    except (OSError, ValueError, TypeError, KeyError):
        return ()


def _read_package_member(path: Path, *, root: Path, maximum_bytes: int) -> bytes:
    with opened_confined_file(path, max_bytes=maximum_bytes, root=root) as opened:
        if isinstance(opened, HostPathRefusal):
            raise ValueError("package member is not a confined regular file")
        payload = opened.read_bytes()
    if isinstance(payload, HostPathRefusal):
        raise ValueError("package member exceeds its byte bound")
    return payload


def _package_member_path(root: Path, member: object) -> tuple[Path, Path] | None:
    if type(member) is not str or not member or "\\" in member:
        return None
    relative = PurePosixPath(member)
    if relative.is_absolute() or relative.as_posix() != member or any(part in {".", ".."} for part in relative.parts):
        return None
    path = root.joinpath(*relative.parts)
    if any(is_link_like(part) for part in (path, *path.parents)):
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    return path, resolved
