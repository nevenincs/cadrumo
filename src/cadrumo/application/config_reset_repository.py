"""Atomic per-file persistence for reset-operation journals.

Journal files live under ``<storage-root>/reset-operations``, outside bucket
directories. Atomicity applies to an individual journal-file write or replace,
not to an entire reset operation. The shared read/write substrate is the
:class:`JournalRepositoryBase`; this module adds the reset-specific
creation-exclusivity and deletion-ownership surface on top.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ..core.config import Settings
from ..core.errors.hierarchy import CadrumoError
from ..core.locks import exclusive_file_lock
from ..core.paths import effective_storage_root
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from .config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
)
from .journal_repository import JournalRepositoryBase

CONFIG_RESET_JOURNAL_DIRNAME = storage_location(StorageCategory.CONFIG_RESET_JOURNAL).subpath


class ConfigResetJournalError(CadrumoError):
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


class ConfigResetJournalRepository(JournalRepositoryBase[ConfigResetOperation]):
    """Persist credential-free journals as atomic individual files.

    The repository provides no reset orchestration, journal-deletion API, or
    cryptographic authenticity guarantee. The atomic read/write substrate is
    inherited from :class:`JournalRepositoryBase`; this class adds
    creation-exclusivity, incompleteness gating, per-operation execution
    locking, and deletion-ownership verification.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        storage_root: Path | None = None,
    ) -> None:
        """Configure the journal repository against the selected storage root."""
        root = effective_storage_root(storage_root, settings=settings)
        super().__init__(
            journal_dirname=CONFIG_RESET_JOURNAL_DIRNAME,
            storage_root=root,
            parse_operation=ConfigResetOperation.model_validate_json,
            error_type=ConfigResetJournalError,
            not_found_type=ConfigResetJournalNotFoundError,
            corrupt_type=ConfigResetJournalCorruptError,
            subject="reset journal",
            id_subject="reset operation",
        )

    def create(self, operation: ConfigResetOperation) -> None:
        """Create a journal while refusing an existing operation identifier."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            if path.exists():
                raise ConfigResetJournalAlreadyExistsError(
                    translated_message="errors.error.error_config_boundary",
                    context={"operation_id": operation.operation_id, "journal_present": True},
                )
            self._write(path, operation)

    def create_exclusive(self, operation: ConfigResetOperation) -> None:
        """Create a journal only when no incomplete reset operation exists."""
        self._ensure_root()
        path = self.path_for(operation.operation_id)
        with exclusive_file_lock(self._lock_target):
            self._raise_if_incomplete()
            if path.exists():
                raise ConfigResetJournalAlreadyExistsError(
                    translated_message="errors.error.error_config_boundary",
                    context={"operation_id": operation.operation_id, "journal_present": True},
                )
            self._write(path, operation)

    def refuse_if_incomplete(self) -> None:
        """Refuse before preflight when another reset journal is incomplete."""
        self._ensure_root()
        with exclusive_file_lock(self._lock_target):
            self._raise_if_incomplete()

    def incomplete(self) -> tuple[ConfigResetOperation, ...]:
        """Return journals whose status is not ``complete``."""
        return tuple(
            operation for operation in self.list() if operation.status is not ConfigResetOperationStatus.COMPLETE
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

    def _raise_if_incomplete(self) -> None:
        incomplete = tuple(
            candidate for candidate in self.list() if candidate.status is not ConfigResetOperationStatus.COMPLETE
        )
        if incomplete:
            raise ConfigResetJournalIncompleteError(
                translated_message="errors.error.error_config_boundary",
                context={"operation_id": incomplete[-1].operation_id, "incomplete_count": len(incomplete)},
            )


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
