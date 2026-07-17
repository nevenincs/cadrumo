"""Durable, non-secret operation state for profile-bundle publication.

The single :func:`~cadrumo.application.user_profile.export_profile_bundle`
authority records the progress of one publication as a credential-free journal
file so a crash in any publication window recovers honestly. Journal files live
under ``<storage-root>/profile-export-operations``, deliberately OUTSIDE both
the target artifact and any bucket directory: the target file is the sensitive
cleartext bundle, so the operation state that describes it carries no bundle
bytes, no passphrase, and no raw tax id -- only the resolved target identity,
purpose, transport, schema version, and derived data categories.

A ``PREPARED`` journal records that a bundle was serialized to a staged
temporary file but not yet atomically published; a ``COMPLETED`` journal
records that the atomic replace and parent-directory fsync durably landed the
target and the completion event fired. Reconciliation reads these states and
never fabricates a completion for an operation that only reached ``PREPARED``.

This is a distinct surface from the sealed recovery archive, which owns its own
confidentiality and restoration semantics and is not folded in here.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import exclusive_file_lock
from ...core.atomic_write import atomic_write_hardened_text
from ...core.config import Settings, load_settings
from ...core.errors import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import validate_utc_aware
from ._bundle_export_contracts import ProfileBundleExportPurpose, ProfileBundleExportTransport

PROFILE_EXPORT_JOURNAL_DIRNAME = "profile-export-operations"
_OPERATION_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


class ProfileBundleExportOperationStatus(StrEnum):
    """Lifecycle state of one durable profile-export publication."""

    PREPARED = "prepared"
    COMPLETED = "completed"


class ProfileBundleExportOperation(BaseModel):
    """Credential-free durable record of one publication's progress."""

    model_config = _STRICT_FROZEN

    operation_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    status: ProfileBundleExportOperationStatus
    profile_id: str = Field(min_length=1)
    display_name: str
    target_identity: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    staged_path: str = Field(min_length=1)
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    bundle_schema_version: int = Field(ge=1)
    data_categories: tuple[str, ...]
    started_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _validate_timestamps(self) -> ProfileBundleExportOperation:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("profile export journal updated_at precedes started_at")
        return self


def derive_export_operation_id(
    *,
    profile_id: str,
    target_identity: str,
    purpose: ProfileBundleExportPurpose,
) -> str:
    """Derive one clock-free operation identifier for a target publication.

    The identifier folds the profile, the resolved target identity, and the
    purpose so a retried export to the same file for the same purpose reconciles
    to the same journal rather than accreting orphan records. The timestamp is a
    non-identity progress field and is deliberately excluded.
    """
    digest = hashlib.sha256()
    digest.update(profile_id.encode(UTF_8_ENCODING))
    digest.update(b"\x00")
    digest.update(target_identity.encode(UTF_8_ENCODING))
    digest.update(b"\x00")
    digest.update(purpose.value.encode(UTF_8_ENCODING))
    return digest.hexdigest()


class ProfileBundleExportJournalError(CadrumoError):
    """Base failure for profile-export journal persistence and validation."""


class ProfileBundleExportJournalNotFoundError(ProfileBundleExportJournalError):
    """Raised when a requested export journal does not exist."""


class ProfileBundleExportJournalCorruptError(ProfileBundleExportJournalError):
    """Raised for unreadable, malformed, schema-invalid, or mismatched journals."""


class ProfileBundleExportJournalRepository:
    """Persist credential-free export journals as atomic individual files.

    The repository provides no publication orchestration and no cryptographic
    authenticity guarantee; it is the durable state store the publication
    service and its reconciliation read and write.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        storage_root: Path | None = None,
    ) -> None:
        resolved_settings = settings or load_settings()
        root = storage_root or resolved_settings.cadrumo_local_storage_root
        self._storage_root = root.expanduser().resolve(strict=False)
        self._root = self._storage_root / PROFILE_EXPORT_JOURNAL_DIRNAME
        self._lock_target = self._root / ".repository"

    @property
    def root(self) -> Path:
        """Return the ``profile-export-operations`` directory under storage."""
        return self._root

    def path_for(self, operation_id: str) -> Path:
        """Return the journal path for one validated operation identifier."""
        _validate_operation_id(operation_id)
        return self._root / f"{operation_id}.json"

    def save(self, operation: ProfileBundleExportOperation) -> None:
        """Atomically write or replace the complete journal for ``operation``."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            self._write(path, operation)

    def load(self, operation_id: str) -> ProfileBundleExportOperation:
        """Load and validate one export-operation journal."""
        if not self._validate_existing_root():
            raise ProfileBundleExportJournalNotFoundError(operation_id)
        path = self.path_for(operation_id)
        if _is_link_like(path):
            raise ProfileBundleExportJournalCorruptError(
                f"profile export journal path cannot be a link: {operation_id}",
            )
        try:
            raw = path.read_text(encoding=UTF_8_ENCODING)
        except FileNotFoundError as exc:
            raise ProfileBundleExportJournalNotFoundError(operation_id) from exc
        except OSError as exc:
            raise ProfileBundleExportJournalCorruptError(
                f"cannot read profile export journal {operation_id}",
            ) from exc
        try:
            operation = ProfileBundleExportOperation.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ProfileBundleExportJournalCorruptError(
                f"invalid profile export journal {operation_id}",
            ) from exc
        if operation.operation_id != operation_id:
            raise ProfileBundleExportJournalCorruptError(
                f"profile export journal filename identity does not match payload: {operation_id}",
            )
        return operation

    def delete(self, operation_id: str) -> None:
        """Remove one journal file once its operation is reconciled or complete."""
        if not self._validate_existing_root():
            return
        path = self.path_for(operation_id)
        with exclusive_file_lock(self._lock_target):
            path.unlink(missing_ok=True)

    def list(self) -> tuple[ProfileBundleExportOperation, ...]:
        """Load JSON journals ordered by start time then operation identifier.

        Non-JSON files are ignored. Corruption in a selected ``*.json`` journal
        propagates rather than being skipped.
        """
        if not self._validate_existing_root():
            return ()
        operations = tuple(self.load(path.stem) for path in self._root.glob("*.json"))
        return tuple(sorted(operations, key=lambda item: (item.started_at, item.operation_id)))

    def prepared(self) -> tuple[ProfileBundleExportOperation, ...]:
        """Return journals still in the ``PREPARED`` (unpublished) state."""
        return tuple(
            operation
            for operation in self.list()
            if operation.status is ProfileBundleExportOperationStatus.PREPARED
        )

    def _ensure_root(self) -> None:
        """Create external journal storage and apply restrictive file modes.

        The directory receives mode ``0700``; journal files receive mode
        ``0600`` in :meth:`_write`. Explicit mode assertions are POSIX-only and
        make no Windows ACL guarantee. A link-like journal root is refused.
        """
        self._storage_root.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(self._root) and _is_link_like(self._root):
            raise ProfileBundleExportJournalError(
                "profile export journal directory cannot be a symlink or junction",
            )
        self._root.mkdir(exist_ok=True)
        if not self._validate_existing_root():
            raise ProfileBundleExportJournalError("profile export journal directory was not created")
        try:
            os.chmod(self._root, _DIRECTORY_MODE)
        except OSError as exc:
            raise ProfileBundleExportJournalError(
                "cannot restrict profile export journal directory permissions",
            ) from exc

    def _validate_existing_root(self) -> bool:
        """Validate a real direct journal directory outside bucket storage."""
        if not os.path.lexists(self._root):
            return False
        if _is_link_like(self._root):
            raise ProfileBundleExportJournalError(
                "profile export journal directory cannot be a symlink or junction",
            )
        if not self._root.is_dir():
            raise ProfileBundleExportJournalError("profile export journal repository path is not a directory")
        resolved_root = self._root.resolve(strict=True)
        if resolved_root.parent != self._storage_root:
            raise ProfileBundleExportJournalError("profile export journal repository escaped the storage root")
        buckets_root = (self._storage_root / "buckets").resolve(strict=False)
        if resolved_root == buckets_root or buckets_root in resolved_root.parents:
            raise ProfileBundleExportJournalError(
                "profile export journal repository must remain outside bucket directories",
            )
        return True

    @staticmethod
    def _write(path: Path, operation: ProfileBundleExportOperation) -> None:
        if os.path.lexists(path) and _is_link_like(path):
            raise ProfileBundleExportJournalError("profile export journal file cannot be a symlink or junction")
        payload = operation.model_dump_json(indent=2) + "\n"
        atomic_write_hardened_text(path, payload, encoding=UTF_8_ENCODING, mode=_FILE_MODE)
        try:
            os.chmod(path, _FILE_MODE)
        except OSError as exc:
            raise ProfileBundleExportJournalError(
                "cannot restrict profile export journal file permissions",
            ) from exc


def _validate_operation_id(operation_id: str) -> None:
    if _OPERATION_ID_PATTERN.fullmatch(operation_id) is None:
        raise ProfileBundleExportJournalError(
            "profile export operation id must be 64 lowercase hexadecimal characters",
        )


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


__all__ = [
    "PROFILE_EXPORT_JOURNAL_DIRNAME",
    "ProfileBundleExportJournalCorruptError",
    "ProfileBundleExportJournalError",
    "ProfileBundleExportJournalNotFoundError",
    "ProfileBundleExportJournalRepository",
    "ProfileBundleExportOperation",
    "ProfileBundleExportOperationStatus",
    "derive_export_operation_id",
]
