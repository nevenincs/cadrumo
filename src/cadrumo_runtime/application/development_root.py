"""Exact-root proof for disposable runtime development storage."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import TypeGuard
from uuid import uuid4

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo.core.storage_environment import host_installed_default_root, normalize_storage_path
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

_MARKER_NAME = ".cadrumo-development-root.json"
_MARKER_PURPOSE = "runtime-development"
_MAXIMUM_MARKER_BYTES = 4096


def _canonical_root(storage_root: Path) -> Path:
    root = normalize_storage_path(storage_root)
    try:
        resolved = root.resolve(strict=True)
        metadata = resolved.stat()
    except OSError:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED) from None
    if not stat.S_ISDIR(metadata.st_mode) or resolved != root:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)
    try:
        installed_default = host_installed_default_root(os.environ)
    except Exception:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED) from None
    if resolved == installed_default:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)
    return resolved


def _storage_identity(root: Path) -> str:
    if sys.platform == "win32":
        from cadrumo_client.transport.windows import WindowsEndpoint

        return WindowsEndpoint(storage_root=root).storage_identity
    from cadrumo_client.transport.posix import posix_storage_identity

    return posix_storage_identity(root)


def _marker_path(root: Path) -> Path:
    return root / _MARKER_NAME


def _marker_document(root: Path, storage_identity: str) -> bytes:
    return json.dumps(
        {
            "version": 1,
            "purpose": _MARKER_PURPOSE,
            "storage_root": str(root),
            "storage_identity": storage_identity,
        },
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _marker_file_is_safe(path: Path) -> os.stat_result:
    metadata = path.lstat()
    current_uid = _current_os_uid() if sys.platform != "win32" else None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        or metadata.st_nlink != 1
        or (sys.platform != "win32" and (current_uid is None or metadata.st_uid != current_uid))
        or (sys.platform != "win32" and metadata.st_mode & 0o077)
    ):
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)
    return metadata


def _current_os_uid() -> int | None:
    """Read the POSIX owner id when this Python build exposes it."""
    getuid = getattr(os, "getuid", None)
    if not callable(getuid):
        return None
    value = getuid()
    return value if isinstance(value, int) else None


def _read_marker(path: Path) -> dict[str, object] | None:
    descriptor = -1
    try:
        before = _marker_file_is_safe(path)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or getattr(opened, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            return None
        chunks: list[bytes] = []
        remaining = _MAXIMUM_MARKER_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > _MAXIMUM_MARKER_BYTES:
            return None
        after = _marker_file_is_safe(path)
        if (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino):
            return None
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_json_members)
        return value if _is_json_object(value) else None
    except (OSError, UnicodeError, ValueError, TypeError, RefusalError):
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Narrow decoded JSON to an object; JSON object member names are strings."""
    return isinstance(value, dict)


def mark_development_root(storage_root: Path) -> Path:
    """Create one bounded marker bound to an existing non-installed root."""
    root = _canonical_root(storage_root)
    identity = _storage_identity(root)
    marker = _marker_path(root)
    current = _read_marker(marker)
    if current is not None and _matches(current, root, identity):
        return marker
    try:
        marker.lstat()
    except FileNotFoundError:
        pass
    else:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)

    payload = _marker_document(root, identity)
    if len(payload) > _MAXIMUM_MARKER_BYTES:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)
    temporary = root / f".{_MARKER_NAME}.{uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(temporary, flags, 0o600)
        if sys.platform != "win32":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, marker)
        temporary.unlink()
        if sys.platform != "win32":
            directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except FileExistsError:
        if verify_development_root(root, identity):
            return marker
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED) from None
    except OSError:
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    if not verify_development_root(root, identity):
        raise RefusalError(RefusalCode.ENDPOINT_UNTRUSTED)
    return marker


def _matches(document: dict[str, object], root: Path, storage_identity: str) -> bool:
    return (
        set(document) == {"version", "purpose", "storage_root", "storage_identity"}
        and type(document.get("version")) is int
        and document["version"] == 1
        and document.get("purpose") == _MARKER_PURPOSE
        and type(document.get("storage_root")) is str
        and document["storage_root"] == str(root)
        and type(document.get("storage_identity")) is str
        and document["storage_identity"] == storage_identity
    )


def verify_development_root(storage_root: Path, storage_identity: str) -> bool:
    """Check the exact marker/root/endpoint binding without proving caller role."""
    try:
        root = _canonical_root(storage_root)
        if _storage_identity(root) != storage_identity:
            return False
        document = _read_marker(_marker_path(root))
        return document is not None and _matches(document, root, storage_identity)
    except Exception:
        return False
