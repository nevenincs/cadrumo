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
from ._config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetTarget,
    ConfigResetTargetPhase,
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


def _require_target_present(
    operation: ConfigResetOperation,
    *,
    operation_id: str,
    bucket_id: str,
) -> ConfigResetTarget:
    target = next(
        (candidate for candidate in operation.targets if candidate.bucket_id == bucket_id),
        None,
    )
    if target is None:
        raise ConfigResetJournalOwnershipError(
            translated_message="errors.error.error_config_boundary",
            context={"operation_id": str(operation_id), "bucket_id": str(bucket_id), "target_contained": False},
        )
    return target


def _require_owned_fingerprint(
    target: ConfigResetTarget,
    *,
    operation_id: str,
    bucket_id: str,
    expected_fingerprint: str,
) -> None:
    fingerprint = target.fingerprint
    if not target.exists_at_snapshot or fingerprint is None or fingerprint.digest != expected_fingerprint:
        raise ConfigResetJournalOwnershipError(
            translated_message="errors.error.error_config_boundary",
            context={"operation_id": str(operation_id), "bucket_id": str(bucket_id), "fingerprint_owned": False},
        )


def _require_approved_retention(
    target: ConfigResetTarget,
    *,
    operation_id: str,
    bucket_id: str,
) -> None:
    retention = target.retention
    if retention is None or (retention.blocks_erase and not retention.override_approved):
        raise ConfigResetJournalOwnershipError(
            translated_message="errors.error.error_config_boundary",
            context={
                "operation_id": str(operation_id),
                "bucket_id": str(bucket_id),
                "retention_decision_approved": False,
            },
        )


def _require_deleting_marker(
    target: ConfigResetTarget,
    *,
    operation_id: str,
    bucket_id: str,
    expected_fingerprint: str,
) -> None:
    marker = target.deletion_marker
    if (
        marker is None
        or marker.operation_id != operation_id
        or marker.bucket_id != bucket_id
        or marker.fingerprint != expected_fingerprint
        or target.phase not in {ConfigResetTargetPhase.DELETING, ConfigResetTargetPhase.DELETED}
    ):
        raise ConfigResetJournalOwnershipError(
            translated_message="errors.error.error_config_boundary",
            context={"operation_id": str(operation_id), "bucket_id": str(bucket_id), "deleting_marker_present": False},
        )


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
        target = _require_target_present(operation, operation_id=operation_id, bucket_id=bucket_id)
        _require_owned_fingerprint(
            target,
            operation_id=operation_id,
            bucket_id=bucket_id,
            expected_fingerprint=expected_fingerprint,
        )
        _require_approved_retention(target, operation_id=operation_id, bucket_id=bucket_id)
        _require_deleting_marker(
            target,
            operation_id=operation_id,
            bucket_id=bucket_id,
            expected_fingerprint=expected_fingerprint,
        )
        return target

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
