"""Durable, non-secret operation state for profile-bundle publication.

The single :func:`~cadrumo.application.user_profile.export_profile_bundle`
authority records the progress of one publication as a credential-free journal
file so a crash in any publication window recovers honestly. Journal files live
under ``<storage-root>/profile-export-operations``, deliberately OUTSIDE both
the target artifact and any bucket directory: the target file is the sensitive
cleartext bundle, so the operation state that describes it carries no bundle
bytes, no passphrase, and no raw tax id -- only the resolved target identity,
purpose, transport, schema version, derived data categories, and the payload
digest.

A ``PREPARED`` journal records that a bundle was serialized to a staged
temporary file but not yet atomically published; a ``COMPLETED`` journal records
that the atomic replace and parent-directory fsync durably landed the target,
with the completion event still owed until the journal is cleared.
Reconciliation completes a durably-published operation -- a ``COMPLETED`` one, or
a ``PREPARED`` one whose destination content matches the recorded digest (the
replace landed but the ``COMPLETED`` transition did not) -- by emitting the owed
event, and clears a ``PREPARED`` operation that never published as an orphan.

This is a distinct surface from the sealed recovery archive, which owns its own
confidentiality and restoration semantics and is not folded in here.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from ...core.config import Settings
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.hex import Hex64Str
from ...core.identity import ContentDigest, ProfileId
from ...core.locks import exclusive_file_lock
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.paths import effective_storage_root
from ...core.time.utc import validate_utc_aware
from ..journal_repository import JournalRepositoryBase
from .bundle_export_contracts import ProfileBundleExportPurpose, ProfileBundleExportTransport

PROFILE_EXPORT_JOURNAL_DIRNAME = "profile-export-operations"
PROFILE_EXPORT_STAGED_TEMP_SUFFIX = ".export-tmp"
_PROFILE_EXPORT_STAGED_NONCE_LENGTH = 8
_ASCII_HEX_LOWER = frozenset("0123456789abcdef")


def profile_export_staged_path(
    destination: Path,
    *,
    process_id: int,
    nonce: str,
) -> Path:
    """Derive the one staged sibling path an export operation may own."""
    return destination.with_name(
        f"{destination.name}.{process_id}.{nonce}{PROFILE_EXPORT_STAGED_TEMP_SUFFIX}",
    )


def is_canonical_profile_export_staged_path(
    destination: Path,
    staged_path: Path,
) -> bool:
    """Return whether staged_path is this destination's generated staging sibling."""
    prefix = f"{destination.name}."
    if staged_path.parent != destination.parent or not staged_path.name.startswith(prefix):
        return False
    remainder = staged_path.name.removeprefix(prefix)
    if not remainder.endswith(PROFILE_EXPORT_STAGED_TEMP_SUFFIX):
        return False
    process_id, separator, nonce = remainder.removesuffix(PROFILE_EXPORT_STAGED_TEMP_SUFFIX).partition(".")
    if (
        not separator
        or not process_id.isascii()
        or not process_id.isdecimal()
        or int(process_id) < 1
        or len(nonce) != _PROFILE_EXPORT_STAGED_NONCE_LENGTH
        or not set(nonce).issubset(_ASCII_HEX_LOWER)
    ):
        return False
    return staged_path == profile_export_staged_path(
        destination,
        process_id=int(process_id),
        nonce=nonce,
    )


class ProfileBundleExportOperationStatus(StrEnum):
    """Lifecycle state of one durable profile-export publication."""

    PREPARED = "prepared"
    COMPLETED = "completed"


class ProfileBundleExportOperation(BaseModel):
    """Credential-free durable record of one publication's progress.

    ``content_sha256`` is the digest of the exact staged payload bytes. Because
    publication moves those bytes into place with :func:`os.replace` rather than
    re-serializing, the published target's digest equals this value, so a
    reconciliation can tell a ``PREPARED`` operation whose replace already landed
    (published, digest matches) from a genuine orphan (digest absent or
    divergent) without a separate durable marker. ``event_occurred_at`` is the
    fixed timestamp the completion event is derived from, so a live publish and a
    later reconciliation emit the byte-identical (idempotent) event.
    """

    model_config = _STRICT_FROZEN

    operation_id: Hex64Str
    status: ProfileBundleExportOperationStatus
    profile_id: ProfileId
    display_name: str
    target_identity: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    staged_path: str = Field(min_length=1)
    content_sha256: ContentDigest
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    bundle_schema_version: int = Field(ge=1)
    data_categories: tuple[str, ...]
    excluded_data_categories: tuple[str, ...] = ()
    started_at: datetime
    updated_at: datetime
    event_occurred_at: datetime

    @model_validator(mode="after")
    def _validate_journal_invariants(self) -> ProfileBundleExportOperation:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        validate_utc_aware(self.event_occurred_at)
        if self.updated_at < self.started_at:
            raise ValueError("profile export journal updated_at precedes started_at")
        if not is_canonical_profile_export_staged_path(
            Path(self.destination),
            Path(self.staged_path),
        ):
            raise ValueError(
                "profile export journal staged_path must be the canonical staging sibling of destination",
            )
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


class UnreadableExportJournal(BaseModel):
    """One journal file the repository could not turn into an operation.

    Carries the file's own identifier and the refusing error's class name rather
    than its message: the id is what an operator needs to find the file, and the
    class name is a stable machine-readable reason that carries no journal
    contents.
    """

    model_config = _STRICT_FROZEN

    journal_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ProfileBundleExportJournalScan(BaseModel):
    """Every journal the repository could read, and every one it could not."""

    model_config = _STRICT_FROZEN

    operations: tuple[ProfileBundleExportOperation, ...]
    unreadable: tuple[UnreadableExportJournal, ...]


def _journal_order(operation: ProfileBundleExportOperation) -> tuple[datetime, str]:
    """Order journals by start time then identifier, stable across both walks."""
    return (operation.started_at, operation.operation_id)


class ProfileBundleExportJournalError(CadrumoError):
    """Base failure for profile-export journal persistence and validation."""


class ProfileBundleExportJournalNotFoundError(ProfileBundleExportJournalError):
    """Raised when a requested export journal does not exist."""


class ProfileBundleExportJournalCorruptError(ProfileBundleExportJournalError):
    """Raised for unreadable, malformed, schema-invalid, or mismatched journals."""


class ProfileBundleExportJournalRepository(JournalRepositoryBase[ProfileBundleExportOperation]):
    """Persist credential-free export journals as atomic individual files.

    The repository provides no publication orchestration and no cryptographic
    authenticity guarantee; it is the durable state store the publication
    service and its reconciliation read and write. The atomic read/write
    substrate is inherited from :class:`JournalRepositoryBase`; this class adds
    journal deletion, an isolating scan, and prepared-state selection.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        storage_root: Path | None = None,
    ) -> None:
        """Bind the journal to the effective storage root for these settings."""
        root = effective_storage_root(storage_root, settings=settings)
        super().__init__(
            journal_dirname=PROFILE_EXPORT_JOURNAL_DIRNAME,
            storage_root=root,
            parse_operation=ProfileBundleExportOperation.model_validate_json,
            error_type=ProfileBundleExportJournalError,
            not_found_type=ProfileBundleExportJournalNotFoundError,
            corrupt_type=ProfileBundleExportJournalCorruptError,
            subject="profile export journal",
            id_subject="profile export operation",
        )

    def delete(self, operation_id: str) -> None:
        """Remove one journal file once its operation is reconciled or complete."""
        if not self._validate_existing_root():
            return
        path = self.path_for(operation_id)
        with exclusive_file_lock(self._lock_target):
            path.unlink(missing_ok=True)

    def scan(self) -> ProfileBundleExportJournalScan:
        """Load every readable journal, reporting the unreadable ones separately.

        The isolating counterpart to :meth:`JournalRepositoryBase.list`. A
        journal that is corrupt, schema-invalid, identity-mismatched, or
        unreadable does not abort the walk and does not disappear either: it
        is reported in ``unreadable`` so the caller can surface it rather
        than silently skipping a record that may still describe cleartext
        bytes on disk.
        """
        operations: list[ProfileBundleExportOperation] = []
        unreadable: list[UnreadableExportJournal] = []
        for path in self._journal_paths():
            try:
                operations.append(self.load(path.stem))
            except ProfileBundleExportJournalNotFoundError:
                # A peer export completing between the directory walk and this
                # load deleted its own journal. That is a healthy success, not
                # an unreadable record: reporting it would tell the operator an
                # unencrypted file may remain when nothing was left behind.
                continue
            except ProfileBundleExportJournalError as exc:
                unreadable.append(
                    UnreadableExportJournal(journal_id=path.stem, reason=type(exc).__name__),
                )
        return ProfileBundleExportJournalScan(
            operations=tuple(sorted(operations, key=_journal_order)),
            unreadable=tuple(sorted(unreadable, key=lambda item: item.journal_id)),
        )

    def prepared(self) -> tuple[ProfileBundleExportOperation, ...]:
        """Return journals still in the ``PREPARED`` (unpublished) state."""
        return tuple(
            operation for operation in self.list() if operation.status is ProfileBundleExportOperationStatus.PREPARED
        )


__all__ = [
    "PROFILE_EXPORT_JOURNAL_DIRNAME",
    "PROFILE_EXPORT_STAGED_TEMP_SUFFIX",
    "ProfileBundleExportJournalCorruptError",
    "ProfileBundleExportJournalError",
    "ProfileBundleExportJournalNotFoundError",
    "ProfileBundleExportJournalRepository",
    "ProfileBundleExportJournalScan",
    "ProfileBundleExportOperation",
    "ProfileBundleExportOperationStatus",
    "UnreadableExportJournal",
    "derive_export_operation_id",
    "is_canonical_profile_export_staged_path",
    "profile_export_staged_path",
]
