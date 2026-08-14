"""Application-owned ports for profile-custody local records.

Application services consume this narrow record store instead of reaching into
the persistence adapter. The default provider resolves the real custody
adapter at the composition boundary; callers can inject the same port when a
different storage root or lifecycle is being composed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel

from ...core import StorageCategory, storage_location
from ...core.paths import effective_storage_root


class ProfileCustodyLocalRecordStore(Protocol):
    """The filesystem capabilities needed by custody-owner authorities."""

    def ensure_directory(self, path: Path) -> None:
        """Create or validate one custody-owned directory."""
        ...

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        """Return the anchored local-record lock context."""
        ...

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        """Read one bounded, no-follow local record."""
        ...

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        """Atomically persist one local record."""
        ...


def canonical_snapshot_payload(model: BaseModel) -> dict[str, object]:
    """Return a snapshot's canonical digest payload without its self-digest."""
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    del payload["self_digest"]
    return payload


def canonical_snapshot_bytes(
    model: BaseModel,
    *,
    maximum_bytes: int,
    limit_error: str,
) -> bytes:
    """Encode one snapshot deterministically, enforcing its byte budget."""
    return canonical_json_bytes(
        model.model_dump(mode="json"),
        maximum_bytes=maximum_bytes,
        limit_error=limit_error,
    )


def canonical_snapshot_digest(
    model: BaseModel,
    *,
    maximum_bytes: int,
    limit_error: str,
) -> str:
    """Digest the canonical snapshot fields that exclude ``self_digest``."""
    return digest_bytes(
        canonical_json_bytes(
            canonical_snapshot_payload(model),
            maximum_bytes=maximum_bytes,
            limit_error=limit_error,
        ),
    )


def canonical_json_bytes(value: object, *, maximum_bytes: int, limit_error: str) -> bytes:
    """Encode JSON with stable ordering and an explicit bounded size."""
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(encoded) > maximum_bytes:
        raise ValueError(limit_error)
    return encoded


def digest_bytes(value: bytes) -> str:
    """Return the canonical SHA-256 digest representation used by snapshots."""
    return f"sha256:{sha256(value).hexdigest()}"


def profile_custody_owner_root(root: Path | None, owner: str) -> Path:
    """Return one canonical owner directory below profile-custody evidence."""
    storage_root = effective_storage_root(root)
    return storage_root / storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE).relative_path() / owner


def ensure_profile_custody_owner_root(store: ProfileCustodyLocalRecordStore, root: Path) -> None:
    """Create the anchored evidence hierarchy needed by one custody owner."""
    for directory in (root.parent.parent, root.parent, root):
        store.ensure_directory(directory)


class _PersistenceCustodyModule(Protocol):
    ensure_profile_custody_local_directory: Callable[[Path], None]
    profile_custody_local_lock: Callable[..., AbstractContextManager[None]]
    read_profile_custody_local_record: Callable[..., bytes]
    write_profile_custody_local_record: Callable[..., None]


class _PersistenceProfileCustodyLocalRecordStore:
    """Adapt the real persistence facade to the application-owned port."""

    def __init__(self) -> None:
        custody = cast(
            _PersistenceCustodyModule,
            import_module("cadrumo.adapters.persistence.storage.custody"),
        )
        self._ensure_directory = custody.ensure_profile_custody_local_directory
        self._lock = custody.profile_custody_local_lock
        self._read = custody.read_profile_custody_local_record
        self._write = custody.write_profile_custody_local_record

    def ensure_directory(self, path: Path) -> None:
        self._ensure_directory(path)

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        return self._lock(path, timeout_seconds=timeout_seconds)

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        return self._read(path, maximum_bytes=maximum_bytes)

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        self._write(path, payload, publish_once=publish_once)


def default_profile_custody_local_record_store() -> ProfileCustodyLocalRecordStore:
    """Return the production custody adapter through the application port."""
    return _PersistenceProfileCustodyLocalRecordStore()


__all__ = [
    "ProfileCustodyLocalRecordStore",
    "canonical_snapshot_bytes",
    "canonical_snapshot_digest",
    "canonical_snapshot_payload",
    "default_profile_custody_local_record_store",
    "ensure_profile_custody_owner_root",
    "profile_custody_owner_root",
]
