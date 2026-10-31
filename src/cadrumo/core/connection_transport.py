"""Canonical transient transport location, instance scope and manager filename declarations."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Final

SOCKET_PATH_LIMIT: Final = 104
MANAGER_SOCKET_DOMAIN: Final = "cadrumo-manager-session-v1"
MANAGER_SOCKET_PREFIX: Final = "manager-"
MANAGER_SOCKET_SUFFIX: Final = ".sock"
MANAGER_SOCKET_DIGEST_BYTES: Final = 16
MANAGER_SOCKET_MAX_IDENTIFIER_BYTES: Final = 128
INSTANCE_ROOT_SCOPE: Final = ".root."
STORAGE_IDENTITY_HEX_DIGITS: Final = 64


def uses_darwin_transport() -> bool:
    """Select the Darwin transient transport: the OS derives that namespace, never the storage root."""
    return sys.platform == "darwin"


def socket_directory(root: Path, *, create: bool = False) -> tuple[Path, bool]:
    """Resolve endpoint storage: the Darwin transient namespace, or the member beneath ``root``."""
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    if uses_darwin_transport():
        from .darwin_transport import darwin_socket_directory

        return darwin_socket_directory(create=create), True
    return root / storage_location(StorageCategory.CONNECTION_SOCKETS).relative_path(), False


def _valid_manager_identifier(manager_id: str) -> bool:
    """Accept only the bounded ASCII identifier grammar used by native socket names."""
    return not (
        not manager_id
        or len(manager_id.encode("utf-8")) > MANAGER_SOCKET_MAX_IDENTIFIER_BYTES
        or manager_id.startswith(".")
        or manager_id.endswith(".")
        or not all(character.isascii() and (character.isalnum() or character in ".-_") for character in manager_id)
    )


def root_scoped_identifier(identifier: str, storage_identity: str) -> str:
    """Scope a per-user instance identifier to one storage root.

    ``storage_identity`` is the hex digest of the root's physical identity that names the
    runtime serving the root, so aliases of one directory share a scope and two roots never do.
    The desktop instance lock and the manager session lock and IPC name use the scoped identifier.
    """
    if not _valid_manager_identifier(identifier) or not (
        len(storage_identity) == STORAGE_IDENTITY_HEX_DIGITS
        and all(character in "0123456789abcdef" for character in storage_identity)
    ):
        raise ValueError("an instance scope requires an ASCII identifier and a lowercase hex storage identity")
    scoped = f"{identifier}{INSTANCE_ROOT_SCOPE}{storage_identity}"
    if not _valid_manager_identifier(scoped):
        raise ValueError("the root-scoped identifier exceeds the identifier bound")
    return scoped


def manager_socket_name(manager_id: str, user: str, session: str) -> str:
    """Encode the channel-qualified native owner/session tuple without path input."""
    if not _valid_manager_identifier(manager_id) or not _native_decimal(user) or not _native_decimal(session):
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
