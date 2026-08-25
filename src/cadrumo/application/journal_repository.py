"""Atomic per-file JSON persistence substrate for operation journals.

A journal repository persists a credential-free typed operation record as an
individual JSON file under a dedicated directory outside bucket storage, with an
atomic hardened write, restrictive ``0700``/``0600`` permissions, symlink and
junction refusal, and a storage-root containment check. This is the
constraint-shape-agnostic half shared by the reset-operation and profile-export
journal repositories: each concrete repository binds its journal directory name,
operation model parser, error types, and message subjects, and adds its own
divergent lifecycle surface (creation exclusivity and ownership verification for
reset; scanning, deletion, and prepared-state selection for profile export) on
top of this base.

Atomicity applies to an individual journal-file write or replace, not to an
entire multi-step operation. The substrate provides no orchestration and no
cryptographic authenticity guarantee.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ..core import (
    HEX_PATTERN_64,
    StorageCategory,
    exclusive_file_lock,
    is_link_like,
    storage_location,
)
from ..core.directory_scan import (
    scan_directory,
)
from ..core.atomic_write import atomic_write_hardened_text
from ..core.errors import CadrumoError
from ..core.external_constants import UTF_8_ENCODING

JOURNAL_OPERATION_ID_PATTERN = re.compile(HEX_PATTERN_64)
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


class JournalOperation(Protocol):
    """Structural contract a journal operation model satisfies.

    Every journal record carries a 64-hex ``operation_id`` (the filename
    identity) and a ``started_at`` timestamp (the primary ordering key), and
    serializes itself to JSON.
    """

    @property
    def operation_id(self) -> str: ...

    @property
    def started_at(self) -> datetime: ...

    def model_dump_json(self, *, indent: int) -> str: ...


class JournalRepositoryBase[T: JournalOperation]:
    """Atomic per-file JSON persistence shared by operation-journal repositories.

    Concrete repositories bind the journal directory name, the operation model
    parser, the error taxonomy, and the message subjects, then layer their own
    divergent lifecycle methods over the shared read/write substrate this base
    provides.
    """

    def __init__(
        self,
        *,
        journal_dirname: str,
        storage_root: Path,
        parse_operation: Callable[[str], T],
        error_type: type[CadrumoError],
        not_found_type: type[CadrumoError],
        corrupt_type: type[CadrumoError],
        subject: str,
        id_subject: str,
    ) -> None:
        self._storage_root = storage_root.expanduser().resolve(strict=False)
        self._root = self._storage_root / journal_dirname
        self._lock_target = self._root / ".repository"
        self._parse_operation = parse_operation
        self._error_type = error_type
        self._not_found_type = not_found_type
        self._corrupt_type = corrupt_type
        self._subject = subject
        self._id_subject = id_subject

    @property
    def root(self) -> Path:
        """Return the journal directory under the storage root."""
        return self._root

    @property
    def lock_target(self) -> Path:
        """Return the sidecar target guarding every journal write.

        Holding it is how a caller (or a crash-window proof) makes a concurrent
        journal write wait; it is a real coordination point, not an
        implementation detail.
        """
        return self._lock_target

    def path_for(self, operation_id: str) -> Path:
        """Return the journal path for one validated operation identifier."""
        self._validate_operation_id(operation_id)
        return self._root / f"{operation_id}.json"

    def save(self, operation: T) -> None:
        """Atomically write or replace the complete journal for ``operation``."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            self._write(path, operation)

    def load(self, operation_id: str) -> T:
        """Load and validate one operation journal.

        Loading refuses missing or unreadable files, malformed JSON,
        schema-invalid payloads, and mismatches between the filename and payload
        identifiers. Validation provides no MAC, signature, or other authenticity
        proof.
        """
        if not self._validate_existing_root():
            raise self._not_found_type(operation_id)
        path = self.path_for(operation_id)
        if is_link_like(path):
            raise self._corrupt_type(f"{self._subject} path cannot be a link: {operation_id}")
        try:
            raw = path.read_text(encoding=UTF_8_ENCODING)
        except FileNotFoundError as exc:
            raise self._not_found_type(operation_id) from exc
        except OSError as exc:
            raise self._corrupt_type(f"cannot read {self._subject} {operation_id}") from exc
        try:
            operation = self._parse_operation(raw)
        except (ValidationError, ValueError) as exc:
            raise self._corrupt_type(f"invalid {self._subject} {operation_id}") from exc
        if operation.operation_id != operation_id:
            raise self._corrupt_type(
                f"{self._subject} filename identity does not match payload: {operation_id}",
            )
        return operation

    def _journal_paths(self) -> tuple[Path, ...]:
        """Return every journal file path, empty when no journal root exists."""
        if not self._validate_existing_root():
            return ()
        return scan_directory(self._root, pattern="*.json")

    def list(self) -> tuple[T, ...]:
        """Load JSON journals ordered by start time then operation identifier.

        Non-JSON files are ignored. Corruption in a selected ``*.json`` journal
        propagates rather than being skipped.
        """
        operations = tuple(self.load(path.stem) for path in self._journal_paths())
        return tuple(sorted(operations, key=lambda item: (item.started_at, item.operation_id)))

    def _ensure_root(self) -> None:
        """Create external journal storage and apply restrictive file modes.

        The directory receives mode ``0700``; journal files receive mode ``0600``
        in :meth:`_write`. Explicit mode assertions are POSIX-only and make no
        Windows ACL guarantee. A link-like journal root is refused.
        """
        self._storage_root.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(self._root) and is_link_like(self._root):
            raise self._error_type(f"{self._subject} directory cannot be a symlink or junction")
        self._root.mkdir(exist_ok=True)
        if not self._validate_existing_root():
            raise self._error_type(f"{self._subject} directory was not created")
        try:
            # Private directory mode; Semgrep's generic file-mode rule is inverted here.
            os.chmod(self._root, _DIRECTORY_MODE)  # nosemgrep
        except OSError as exc:
            raise self._error_type(f"cannot restrict {self._subject} directory permissions") from exc

    def _validate_existing_root(self) -> bool:
        """Validate a real direct journal directory outside bucket storage.

        Link-like roots and redirected resolved locations are refused. This is a
        location check, not protection against malicious concurrent path
        replacement.
        """
        if not os.path.lexists(self._root):
            return False
        if is_link_like(self._root):
            raise self._error_type(f"{self._subject} directory cannot be a symlink or junction")
        if not self._root.is_dir():
            raise self._error_type(f"{self._subject} repository path is not a directory")
        resolved_root = self._root.resolve(strict=True)
        if resolved_root.parent != self._storage_root:
            raise self._error_type(f"{self._subject} repository escaped the storage root")
        buckets_root = (self._storage_root / storage_location(StorageCategory.BUCKETS).relative_path()).resolve(
            strict=False,
        )
        if resolved_root == buckets_root or buckets_root in resolved_root.parents:
            raise self._error_type(f"{self._subject} repository must remain outside bucket directories")
        return True

    def _write(self, path: Path, operation: T) -> None:
        if os.path.lexists(path) and is_link_like(path):
            raise self._error_type(f"{self._subject} file cannot be a symlink or junction")
        payload = operation.model_dump_json(indent=2) + "\n"
        atomic_write_hardened_text(path, payload, encoding=UTF_8_ENCODING, mode=_FILE_MODE)
        try:
            os.chmod(path, _FILE_MODE)
        except OSError as exc:
            raise self._error_type(f"cannot restrict {self._subject} file permissions") from exc

    def _validate_operation_id(self, operation_id: str) -> None:
        if JOURNAL_OPERATION_ID_PATTERN.fullmatch(operation_id) is None:
            raise self._error_type(f"{self._id_subject} id must be 64 lowercase hexadecimal characters")


__all__ = [
    "JournalOperation",
    "JournalRepositoryBase",
]
