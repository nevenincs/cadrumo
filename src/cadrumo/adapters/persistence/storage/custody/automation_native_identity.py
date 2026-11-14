"""Native automation credential namespaces and exact storage-root identity."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from .....core.hashing import sha256_hex
from .automation_secret_target import AUTOMATION_NAMESPACE_PREFIX

CONTROL_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}control-anchor.v1"


WRAP_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}grant-wrap.v1"


CLIENT_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}client-key.v1"


def automation_root_digest(root: Path) -> str:
    """Return the one-way storage-root identity that leads every native automation account of ``root``."""
    return sha256_hex(str(root.resolve()).encode("utf-8"))


def automation_native_account(root: Path, installation_id: UUID, profile_id: UUID) -> str:
    """Name one profile's native credentials, scoped to the storage root they belong to."""
    return f"{automation_root_digest(root)}/{installation_id}/{profile_id}"
