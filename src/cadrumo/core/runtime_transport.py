"""Canonical transient transport location and manager filename declarations."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Final

from .storage_environment import StorageMode, storage_mode

RUNTIME_SOCKET_PATH_LIMIT: Final = 104
MANAGER_SOCKET_DOMAIN: Final = "cadrumo-manager-session-v1"
MANAGER_SOCKET_PREFIX: Final = "manager-"
MANAGER_SOCKET_SUFFIX: Final = ".sock"
MANAGER_SOCKET_DIGEST_BYTES: Final = 16
MANAGER_SOCKET_MAX_IDENTIFIER_BYTES: Final = 128


def uses_darwin_transport(*, explicit: bool) -> bool:
    """Select the native default from package mode, never from a storage-root pin."""
    return sys.platform == "darwin" and not explicit and storage_mode().mode is StorageMode.INSTALLED


def runtime_socket_directory(root: Path, *, create: bool = False) -> tuple[Path, bool]:
    """Resolve endpoint storage while preserving explicit Settings/namespace authority."""
    from .config import load_settings
    from .storage_environment import storage_directory
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    settings = load_settings()
    location = storage_location(StorageCategory.RUNTIME_SOCKETS)
    field = location.settings_field
    if field is None:
        raise ValueError("runtime sockets require a declared operator setting")
    if os.environ.get(field.upper(), "").strip():
        return storage_directory(field.upper(), location.subpath, root=root), False
    explicit = field in settings.model_fields_set
    if uses_darwin_transport(explicit=explicit):
        from .darwin_transport import darwin_socket_directory

        return darwin_socket_directory(create=create), True
    if explicit:
        return Path(getattr(settings, field)), False
    return storage_directory(field.upper(), location.subpath, root=root), False


def manager_socket_name(manager_id: str, user: str, session: str) -> str:
    """Encode the channel-qualified native owner/session tuple without path input."""
    if (
        not manager_id
        or len(manager_id.encode("utf-8")) > MANAGER_SOCKET_MAX_IDENTIFIER_BYTES
        or manager_id.startswith(".")
        or manager_id.endswith(".")
        or not all(character.isascii() and (character.isalnum() or character in ".-_") for character in manager_id)
        or not _native_decimal(user)
        or not _native_decimal(session)
    ):
        raise ValueError("manager socket identity requires an ASCII identifier and canonical native u32 coordinates")
    encoded = json.dumps(
        [MANAGER_SOCKET_DOMAIN, manager_id, user, session], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).digest()[:MANAGER_SOCKET_DIGEST_BYTES]
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{MANAGER_SOCKET_PREFIX}{token}{MANAGER_SOCKET_SUFFIX}"


def _native_decimal(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 10
        and value.isascii()
        and value.isdecimal()
        and str(int(value)) == value
        and int(value) <= 2**32 - 1
    )
