"""Atomic per-file persistence for reset-operation journals.

Journal files live under ``<storage-root>/reset-operations``, outside bucket
directories. Atomicity applies to an individual journal-file write or replace,
not to an entire reset operation.
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from ..core import exclusive_file_lock
from ..core.atomic_write import atomic_write_hardened_text
from ..core.config import Settings, load_settings
from ..core.errors import AeatError
from ..core.external_constants import UTF_8_ENCODING
from ._config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetTarget,
    ConfigResetTargetPhase,
)

CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"
_OPERATION_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


class ConfigResetJournalError(AeatError):
    """Base failure for reset-journal persistence and validation."""


class ConfigResetJournalAlreadyExistsError(ConfigResetJournalError):
    """Raised when create targets an operation id already on disk."""


class ConfigResetJournalNotFoundError(ConfigResetJournalError):
    """Raised when a requested reset journal does not exist."""


class ConfigResetJournalCorruptError(ConfigResetJournalError):
    """Raised for unreadable, malformed, schema-invalid, or mismatched journals."""


class ConfigResetJournalOwnershipError(ConfigResetJournalError):
    """Raised when a journal lacks the required target deletion evidence."""


class ConfigResetJournalIncompleteError(ConfigResetJournalError):
    """Raised when a new operation would overlap an incomplete reset."""


class ConfigResetJournalRepository:
    """Persist credential-free journals as atomic individual files.

    The repository provides no reset orchestration, journal-deletion API, or
    cryptographic authenticity guarantee.
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
        self._root = self._storage_root / CONFIG_RESET_JOURNAL_DIRNAME
        self._lock_target = self._root / ".repository"

    @property
    def root(self) -> Path:
        """Return the ``reset-operations`` directory under the storage root."""
        return self._root

    def path_for(self, operation_id: str) -> Path:
        """Return the journal path for one validated operation identifier."""
        _validate_operation_id(operation_id)
        return self._root / f"{operation_id}.json"

    def create(self, operation: ConfigResetOperation) -> None:
        """Create a journal while refusing an existing operation identifier."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            if path.exists():
                raise ConfigResetJournalAlreadyExistsError(operation.operation_id)
            self._write(path, operation)

    def create_exclusive(self, operation: ConfigResetOperation) -> None:
        """Create a journal only when no incomplete reset operation exists."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            self._raise_if_incomplete()
            if path.exists():
                raise ConfigResetJournalAlreadyExistsError(operation.operation_id)
            self._write(path, operation)

    def refuse_if_incomplete(self) -> None:
        """Refuse before preflight when another reset journal is incomplete."""
        self._ensure_root()
        with exclusive_file_lock(self._lock_target):
            self._raise_if_incomplete()

    def save(self, operation: ConfigResetOperation) -> None:
        """Atomically write or replace the complete journal for ``operation``."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            self._write(path, operation)

    def load(self, operation_id: str) -> ConfigResetOperation:
        """Load and validate one reset-operation journal.

        Loading refuses missing or unreadable files, malformed JSON,
        schema-invalid payloads, and mismatches between the filename and
        payload identifiers. Validation provides no MAC, signature, or other
        authenticity proof.
        """
        if not self._validate_existing_root():
            raise ConfigResetJournalNotFoundError(operation_id)
        path = self.path_for(operation_id)
        if _is_link_like(path):
            raise ConfigResetJournalCorruptError(
                f"reset journal path cannot be a link: {operation_id}",
            )
        try:
            raw = path.read_text(encoding=UTF_8_ENCODING)
        except FileNotFoundError as exc:
            raise ConfigResetJournalNotFoundError(operation_id) from exc
        except OSError as exc:
            raise ConfigResetJournalCorruptError(f"cannot read reset journal {operation_id}") from exc
        try:
            operation = ConfigResetOperation.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ConfigResetJournalCorruptError(f"invalid reset journal {operation_id}") from exc
        if operation.operation_id != operation_id:
            raise ConfigResetJournalCorruptError(
                f"reset journal filename identity does not match payload: {operation_id}",
            )
        return operation

    def list(self) -> tuple[ConfigResetOperation, ...]:
        """Load JSON journals ordered by start time then operation identifier.

        Non-JSON files are ignored. Corruption in a selected ``*.json`` journal
        propagates rather than being skipped.
        """
        if not self._validate_existing_root():
            return ()
        operations = tuple(self.load(path.stem) for path in self._root.glob("*.json"))
        return tuple(sorted(operations, key=lambda item: (item.started_at, item.operation_id)))

    def incomplete(self) -> tuple[ConfigResetOperation, ...]:
        """Return journals whose status is not ``complete``."""
        return tuple(
            operation
            for operation in self.list()
            if operation.status is not ConfigResetOperationStatus.COMPLETE
        )

    def latest(self) -> ConfigResetOperation | None:
        """Return the last journal in repository ordering, or ``None``."""
        operations = self.list()
        return operations[-1] if operations else None

    @contextmanager
    def operation_lock(self, operation_id: str) -> Generator[None]:
        """Serialize start or resume execution for one operation identifier."""
        self._ensure_root()
        with exclusive_file_lock(self.path_for(operation_id)):
            yield

    def verify_deletion_ownership(
        self,
        *,
        operation_id: str,
        bucket_id: str,
        expected_fingerprint: str,
    ) -> ConfigResetTarget:
        """Verify journal ownership of one target deletion.

        The target must have existed in the snapshot with the expected
        fingerprint, carry a resolved retention decision, and hold a matching
        deletion marker in the ``deleting`` or ``deleted`` phase.
        """
        operation = self.load(operation_id)
        target = next(
            (candidate for candidate in operation.targets if candidate.bucket_id == bucket_id),
            None,
        )
        if target is None:
            raise ConfigResetJournalOwnershipError(
                f"reset operation {operation_id} does not contain target {bucket_id}",
            )
        fingerprint = target.fingerprint
        if (
            not target.exists_at_snapshot
            or fingerprint is None
            or fingerprint.digest != expected_fingerprint
        ):
            raise ConfigResetJournalOwnershipError(
                f"reset operation {operation_id} does not own fingerprint for target {bucket_id}",
            )
        retention = target.retention
        if retention is None or (retention.blocks_erase and not retention.override_approved):
            raise ConfigResetJournalOwnershipError(
                f"reset operation {operation_id} has no approved retention decision for target {bucket_id}",
            )
        marker = target.deletion_marker
        if (
            marker is None
            or marker.operation_id != operation_id
            or marker.bucket_id != bucket_id
            or marker.fingerprint != expected_fingerprint
            or target.phase not in {ConfigResetTargetPhase.DELETING, ConfigResetTargetPhase.DELETED}
        ):
            raise ConfigResetJournalOwnershipError(
                f"reset operation {operation_id} has no deleting marker for target {bucket_id}",
            )
        return target

    def _ensure_root(self) -> None:
        """Create external journal storage and apply restrictive file modes.

        The directory receives mode ``0700``. Journal files receive mode
        ``0600`` in :meth:`_write`; explicit mode assertions are POSIX-only and
        make no Windows ACL guarantee. A symlink or junction at the journal
        root is refused.
        """
        self._storage_root.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(self._root) and _is_link_like(self._root):
            raise ConfigResetJournalError("reset journal directory cannot be a symlink or junction")
        self._root.mkdir(exist_ok=True)
        if not self._validate_existing_root():
            raise ConfigResetJournalError("reset journal directory was not created")
        try:
            os.chmod(self._root, _DIRECTORY_MODE)
        except OSError as exc:
            raise ConfigResetJournalError("cannot restrict reset journal directory permissions") from exc

    def _validate_existing_root(self) -> bool:
        """Validate a real direct journal directory outside bucket storage.

        Link-like roots and redirected resolved locations are refused. This is
        a location check, not protection against malicious concurrent path
        replacement.
        """
        if not os.path.lexists(self._root):
            return False
        if _is_link_like(self._root):
            raise ConfigResetJournalError("reset journal directory cannot be a symlink or junction")
        if not self._root.is_dir():
            raise ConfigResetJournalError("reset journal repository path is not a directory")
        resolved_root = self._root.resolve(strict=True)
        if resolved_root.parent != self._storage_root:
            raise ConfigResetJournalError("reset journal repository escaped the storage root")
        buckets_root = (self._storage_root / "buckets").resolve(strict=False)
        if resolved_root == buckets_root or buckets_root in resolved_root.parents:
            raise ConfigResetJournalError("reset journal repository must remain outside bucket directories")
        return True

    @staticmethod
    def _write(path: Path, operation: ConfigResetOperation) -> None:
        if os.path.lexists(path) and _is_link_like(path):
            raise ConfigResetJournalError("reset journal file cannot be a symlink or junction")
        payload = operation.model_dump_json(indent=2) + "\n"
        atomic_write_hardened_text(
            path,
            payload,
            encoding=UTF_8_ENCODING,
            mode=_FILE_MODE,
        )
        try:
            os.chmod(path, _FILE_MODE)
        except OSError as exc:
            raise ConfigResetJournalError("cannot restrict reset journal file permissions") from exc

    def _raise_if_incomplete(self) -> None:
        incomplete = tuple(
            candidate
            for candidate in self.list()
            if candidate.status is not ConfigResetOperationStatus.COMPLETE
        )
        if incomplete:
            raise ConfigResetJournalIncompleteError(incomplete[-1].operation_id)


def _validate_operation_id(operation_id: str) -> None:
    if _OPERATION_ID_PATTERN.fullmatch(operation_id) is None:
        raise ConfigResetJournalError("reset operation id must be 64 lowercase hexadecimal characters")


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


__all__ = [
    "CONFIG_RESET_JOURNAL_DIRNAME",
    "ConfigResetJournalAlreadyExistsError",
    "ConfigResetJournalCorruptError",
    "ConfigResetJournalError",
    "ConfigResetJournalIncompleteError",
    "ConfigResetJournalNotFoundError",
    "ConfigResetJournalOwnershipError",
    "ConfigResetJournalRepository",
]
