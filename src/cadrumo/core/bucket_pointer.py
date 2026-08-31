"""Strict current-only record for the active-profile pointer.

The pointer is one durable, plaintext coordination record under the storage
root. It names either a selected bucket or an explicit absence and carries the
monotonic transition coordinate used by every pointer consumer. The record is
not a profile manifest or a profile-lifecycle assertion: it only records the
currently selected bucket.
"""

from __future__ import annotations

import os
import stat
import sys
import time
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field, model_validator

from .models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .identity import BucketId

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from .errors.hierarchy import CadrumoError

POINTER_SCHEMA_VERSION: Final[Literal[2]] = 2


class BucketPointer(BaseModel):
    """One strict active-profile selection and its durable transition revision.

    ``selection`` is deliberately explicit because TOML has no null scalar.
    A selected record carries exactly one bucket id; an absent record is the
    persisted tombstone written by clear. The physically absent initial file
    observes as an absent record at revision zero and is never accepted as an
    on-disk compatibility format.
    """

    model_config = _STRICT_FROZEN

    selection: Literal["absent", "selected"]
    bucket_id: BucketId | None = None
    transition_revision: int = Field(ge=0)
    schema_version: Literal[2]

    @model_validator(mode="after")
    def _validate_selection(self) -> BucketPointer:
        if (self.selection == "selected") != (self.bucket_id is not None):
            raise ValueError("pointer selection and bucket id must agree")
        return self

    @classmethod
    def absent(cls, *, transition_revision: int) -> BucketPointer:
        """Construct the explicit absent-selection tombstone."""
        return cls(
            selection="absent",
            bucket_id=None,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    @classmethod
    def selected(cls, *, bucket_id: str, transition_revision: int) -> BucketPointer:
        """Construct one selected current-format record."""
        return cls(
            selection="selected",
            bucket_id=bucket_id,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    def to_toml(self) -> str:
        """Return the deterministic strict current-format TOML payload."""
        lines = [f'selection = "{self.selection}"']
        if self.bucket_id is not None:
            bucket_id_escaped = self.bucket_id.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'bucket_id = "{bucket_id_escaped}"')
        lines.extend(
            (
                f"transition_revision = {self.transition_revision}",
                f"schema_version = {self.schema_version}",
            )
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_toml(cls, text: str) -> BucketPointer:
        """Strictly parse a current-format pointer record."""
        return cls.model_validate(tomllib.loads(text))


def pointer_path(root: Path) -> Path:
    """Return the active-profile record path beneath ``root``."""
    from .storage_taxonomy import StorageCategory, storage_location

    return root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()


_POINTER_READ_RETRY_SECONDS = 1.0
_POINTER_READ_POLL_SECONDS = 0.02
_POINTER_READ_MAX_WAIT_SECONDS = 15.0
_POINTER_WRITE_RETRY_SECONDS = 1.0
_POINTER_MAXIMUM_BYTES = 1024


def _pointer_entry_signature(target: Path) -> tuple[str, int, int] | None:
    from .paths import path_stat_fingerprint

    try:
        return path_stat_fingerprint(target)
    except OSError:
        return None


def _read_pointer_bytes(target: Path) -> bytes | None:
    """Read one complete record, waiting out a Windows replacement race."""

    def read_once() -> bytes:
        from ._link_safety import is_link_like

        if is_link_like(target):
            raise OSError("active-profile pointer must not be link-like")
        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _POINTER_MAXIMUM_BYTES:
                raise OSError("active-profile pointer must be a bounded regular file")
            payload = os.read(descriptor, _POINTER_MAXIMUM_BYTES + 1)
            if len(payload) != metadata.st_size or len(payload) > _POINTER_MAXIMUM_BYTES:
                raise OSError("active-profile pointer changed during read")
            return payload
        finally:
            os.close(descriptor)

    if sys.platform != "win32":
        try:
            return read_once()
        except FileNotFoundError:
            return None
    from ._windows_contention import is_windows_contention

    started = time.monotonic()
    deadline = started + _POINTER_READ_RETRY_SECONDS
    ceiling = started + _POINTER_READ_MAX_WAIT_SECONDS
    signature = _pointer_entry_signature(target)
    while True:
        try:
            return read_once()
        except FileNotFoundError:
            return None
        except PermissionError as exc:
            now = time.monotonic()
            current = _pointer_entry_signature(target)
            if current != signature:
                signature = current
                deadline = now + _POINTER_READ_RETRY_SECONDS
            transient_windows_refusal = sys.platform == "win32" and (
                is_windows_contention(exc) or getattr(exc, "winerror", None) is None
            )
            if not transient_windows_refusal or now >= deadline or now >= ceiling:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)


def read_pointer(root: Path) -> BucketPointer:
    """Observe the optional selection and durable current coordinate once."""
    raw = _read_pointer_bytes(pointer_path(root))
    if raw is None:
        return BucketPointer.absent(transition_revision=0)
    return BucketPointer.from_toml(raw.decode("utf-8"))


def _await_uncontended(operation: Callable[[], None]) -> None:
    """Retry a bounded Windows sharing refusal without masking permanent failures."""
    from ._windows_contention import is_windows_contention

    deadline = time.monotonic() + _POINTER_WRITE_RETRY_SECONDS
    while True:
        try:
            operation()
        except PermissionError as exc:
            # Windows can surface a sharing refusal from ``os.open`` without a
            # populated ``winerror``. A bounded retry is safe for every
            # Windows PermissionError: an ACL or directory refusal remains a
            # refusal once the short contention window expires, while a peer's
            # reader handle releases and permits the atomic publication.
            transient_windows_refusal = sys.platform == "win32" and (
                is_windows_contention(exc) or getattr(exc, "winerror", None) is None
            )
            if not transient_windows_refusal or time.monotonic() >= deadline:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)
            continue
        return


def write_pointer(root: Path, pointer: BucketPointer) -> None:
    """Atomically replace the one strict pointer record under its owner lock."""
    from ._fsync import fsync_parent_dir
    from .atomic_write import atomic_write_hardened_bytes

    target = pointer_path(root)
    _await_uncontended(lambda: atomic_write_hardened_bytes(target, pointer.to_toml().encode("utf-8")))
    fsync_parent_dir(target)


def resolve_active_bucket_id() -> str | None:
    """Resolve a process override or one current persisted selection."""
    from .config import load_settings

    settings = load_settings()
    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    return read_pointer(settings.cadrumo_local_storage_root).bucket_id


def require_active_bucket_id() -> str:
    """Return the selected bucket or raise the canonical no-profile refusal."""
    from .errors.hierarchy import NoActiveProfileError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise NoActiveProfileError(translated_message="application.workflow.errors.no_active_profile_bucket")
    return bucket_id


def resolve_repository_bucket_id(bucket_id: str | None, *, error_type: type[CadrumoError]) -> str:
    """Resolve an explicit bucket or the current pointer selection."""
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "blank_explicit_bucket_id"},
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "missing_active_profile_bucket"},
        )
    return active


__all__ = [
    "POINTER_SCHEMA_VERSION",
    "BucketPointer",
    "pointer_path",
    "read_pointer",
    "require_active_bucket_id",
    "resolve_active_bucket_id",
    "resolve_repository_bucket_id",
    "write_pointer",
]
