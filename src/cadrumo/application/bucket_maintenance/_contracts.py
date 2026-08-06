"""Pydantic command + result records for :class:`BucketMaintenanceService`.

Used by: :mod:`~._service` to implement bucket operations.

The contract records sit at the package boundary so a programmatic
caller (the CLI handler, a future MCP surface) gets the same typed
input + output shape that the service consumes. Closed-value axes are
typed as their core enums per the architecture-boundaries discipline.
Every bucket selector is a :class:`BucketId`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ...core.time import UtcInstant
from ...domain.retention import RetentionFloorAssessment
from ...domain.user_profile import UserProfileStatus
from .._bucket_deletion_contracts import BucketDeletionFingerprint

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AssessBucketDeletionCommand(BaseModel):
    """Read-only deletion-assessment intent for one explicit bucket."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId


class BucketDeletionAssessment(BaseModel):
    """Assessment of an explicit bucket target before deletion.

    The existing and absent forms are mutually exclusive. An existing
    assessment carries the bucket label, lifecycle status, deletion
    fingerprint, and :class:`RetentionFloorAssessment`; an absent assessment
    carries none of those values.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    exists: bool
    label: str | None = Field(default=None, min_length=1, max_length=160)
    status: UserProfileStatus | None = None
    fingerprint: BucketDeletionFingerprint | None = None
    retention: RetentionFloorAssessment | None = None

    @model_validator(mode="after")
    def _validate_existence_shape(self) -> BucketDeletionAssessment:
        present_fields = (self.label, self.status, self.fingerprint, self.retention)
        if self.exists and any(value is None for value in present_fields):
            raise ValueError("existing deletion assessment requires label, status, fingerprint, and retention")
        if not self.exists and any(value is not None for value in present_fields):
            raise ValueError("absent deletion assessment cannot carry bucket metadata")
        return self


class RenameBucketCommand(BaseModel):
    """Operator request to relabel a bucket.

    ``bucket_id`` is the stable :class:`BucketId`; only the
    operator-visible label moves. The service forwards the relabel to
    the profile-rename single-writer primitive, which holds the
    cross-store atomicity (encrypted record ``display_name`` and
    plaintext manifest ``label`` move together).
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    new_label: str = Field(min_length=1, max_length=160)


class RenameBucketResult(BaseModel):
    """Outcome of a successful rename.

    Carries the prior label so the operator-facing emitter can render
    the before / after pair without re-reading the manifest. The
    ``occurred_at`` instant is the same instant carried by the
    ``BUCKET_RENAMED`` bucket event.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    previous_label: str = Field(min_length=1, max_length=160)
    new_label: str = Field(min_length=1, max_length=160)
    occurred_at: UtcInstant


class DeleteBucketCommand(BaseModel):
    """Operator request to destructively erase a bucket.

    ``confirmed=True`` is required at the service boundary so a
    programmatic caller observes the same guarantee the CLI ``--yes``
    flag provides. The active bucket cannot be deleted; the operator
    must switch profiles first.

    ``acknowledge_retention_override`` is the explicit legal-retention
    override: when a filed tax record is still inside its four-year LGT
    retention window (Ley 58/2003 art. 66/70) the erase is refused
    unless this flag is ``True`` AND ``retention_override_reason`` is a
    non-empty justification the audit trail records.

    The optional ``reset_operation_id`` and
    ``expected_deletion_fingerprint`` pair provides caller-owned operation
    context. The service verifies that context against the durable reset
    journal before accepting an operation-owned deletion.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    confirmed: bool = False
    acknowledge_retention_override: bool = False
    retention_override_reason: str | None = Field(default=None, min_length=1, max_length=512)
    reset_operation_id: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    expected_deletion_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )

    @model_validator(mode="after")
    def _validate_reset_ownership(self) -> DeleteBucketCommand:
        owns_reset_delete = self.reset_operation_id is not None
        has_fingerprint = self.expected_deletion_fingerprint is not None
        if owns_reset_delete != has_fingerprint:
            raise ValueError("reset deletion ownership requires operation id and expected fingerprint together")
        return self


class DeleteBucketResult(BaseModel):
    """Outcome of an actual deletion or an accepted already-absent target.

    ``previous_label`` carries the deleted bucket's observed prior label and
    is ``None`` for an accepted already-absent target. The deletion
    fingerprint is observed for an actual deletion or carries the caller's
    expected value for an accepted already-absent target.
    ``retention_override_used`` records whether a still-retained record
    was erased under the explicit legal-retention override, and
    ``latest_safe_erase_date`` names the instant the erased set would
    otherwise have become safe to erase (``None`` when nothing was
    inside its window).
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    previous_label: str | None = Field(default=None, min_length=1, max_length=160)
    occurred_at: UtcInstant
    retention_override_used: bool = False
    latest_safe_erase_date: UtcInstant | None = None
    deletion_fingerprint: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    reset_operation_id: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    already_absent: bool = False


class ArchiveBucketCommand(BaseModel):
    """Operator request to move a bucket into reversible dormancy.

    Unlike :class:`DeleteBucketCommand`, ``archive`` is a soft-only
    tombstone: it never removes the bucket directory, so
    :class:`RestoreBucketCommand` can bring the same bucket back.
    ``confirmed=True`` mirrors ``delete``'s boundary contract so a
    programmatic caller observes the same guarantee the CLI ``--yes``
    flag provides. The active bucket cannot be archived; the operator
    must switch profiles first.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    confirmed: bool = False


class ArchiveBucketResult(BaseModel):
    """Outcome of a successful bucket archive.

    Carries the archived bucket's label so the operator-facing emitter
    can render a confirming line without re-reading the manifest.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str = Field(min_length=1, max_length=160)
    occurred_at: UtcInstant


class RestoreBucketCommand(BaseModel):
    """Operator request to bring an archived bucket back to active status.

    Symmetric inverse of :class:`ArchiveBucketCommand`. Refuses when the
    target bucket is not currently archived (tombstoned), so a restore
    never silently no-ops against an already-live bucket.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId


class RestoreBucketResult(BaseModel):
    """Outcome of a successful bucket restore."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str = Field(min_length=1, max_length=160)
    occurred_at: UtcInstant


class BrowseBucketCommand(BaseModel):
    """Operator request to enumerate a bucket's namespace inventory.

    The current shape is namespace-level only: it returns each
    namespace and its row count without decrypting payloads. Key-level
    browse requires decryption and a ``SensitivityClass`` redaction
    policy, both deferred to a follow-up change.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    namespace_filter: str | None = Field(default=None, min_length=1, max_length=128)


class BucketNamespaceInventoryRow(BaseModel):
    """One row of the namespace-inventory browse result."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    row_count: int = Field(ge=0)


class BrowseBucketResult(BaseModel):
    """Namespace-level browse outcome.

    Returns one row per namespace present in the bucket (optionally
    substring-filtered by ``namespace_filter``), each carrying the
    stored-row count. Read-only; emits no bucket event.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    rows: tuple[BucketNamespaceInventoryRow, ...]


class DiskUsageBucketCommand(BaseModel):
    """Operator request to measure a bucket's on-disk footprint.

    Reads only filesystem metadata (``os.stat`` sizes) under
    ``<cadrumo_local_storage_root>/buckets/<bucket_id>/``; it never opens the
    encrypted SQLite database or decrypts a secure-object payload, so no
    master key or active-bucket session is required. This makes the
    measurement safe to run against a non-active, even archived, bucket —
    the same non-active-safe posture :func:`~._sandbox.preview_discard_sandbox`
    already relies on for its namespace preview.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId


class BucketDiskUsageSubdirRow(BaseModel):
    """One on-disk subdirectory's byte total in a disk-usage report.

    ``subdir`` names one of the bucket layout's fixed subdirectories
    (``db``, ``blobs``, ``audit``); the row is emitted even when the
    subdirectory is empty (``total_bytes=0``, ``file_count=0``) so a
    caller can rely on exactly the layout's three rows always being
    present.
    """

    model_config = STRICT_FROZEN_CONFIG

    subdir: str = Field(min_length=1)
    total_bytes: int = Field(ge=0)
    file_count: int = Field(ge=0)


class DiskUsageBucketResult(BaseModel):
    """Bucket on-disk footprint outcome.

    ``total_bytes`` is the sum of every regular file under the bucket's
    directory tree (``db`` + ``blobs`` + ``audit``, plus the bucket's own
    manifest file); ``subdirs`` breaks that total down per fixed
    subdirectory. Read-only; emits no bucket event.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    total_bytes: int = Field(ge=0)
    subdirs: tuple[BucketDiskUsageSubdirRow, ...]


class ExportBucketCommand(BaseModel):
    """Operator request to export a bucket as a sealed archive.

    The ``output_path`` is operator-specified; the service refuses to
    overwrite an existing target. The ``recovery_wrap_passphrase``
    field is optional: when present the service derives a
    recovery-passphrase KEK and emits a 3-member archive (including
    ``recovery.wrap``); when absent the service uses the bucket's
    active KEK and emits a 2-member archive without recovery-wrap.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    output_path: Path
    recovery_wrap_passphrase: str | None = Field(default=None, min_length=8, max_length=512)


class ExportBucketResult(BaseModel):
    """Outcome of a successful bucket export.

    Carries the written archive path plus the manifest digest recorded
    in the sealed archive header. The digest is bound into the payload's
    AEAD associated data, so import refuses a tampered header at
    decryption; operator emitters render the path so the operator can
    locate the file for backup or transfer.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    output_path: Path
    manifest_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    recovery_wrap_present: bool
    occurred_at: UtcInstant


class ImportBucketCommand(BaseModel):
    """Operator request to import a sealed bucket archive.

    The ``source_path`` is operator-specified. The service refuses
    when the archive's ``bucket_id`` collides with an existing live
    profile unless ``force_replace`` is ``True``; when the source
    archive carries a recovery-wrap member, the operator MUST supply
    the matching ``recovery_wrap_passphrase``.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_path: Path
    force_replace: bool = False
    recovery_wrap_passphrase: str | None = Field(default=None, min_length=8, max_length=512)


class ImportBucketResult(BaseModel):
    """Outcome of a successful bucket import.

    Carries the imported :class:`BucketId` and the manifest digest the
    archive header declared. The digest is evidence of the sealed
    archive header that authenticated the payload; it is not recomputed
    against the freshly provisioned host manifest because import-host
    lifecycle timestamps legitimately differ.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    manifest_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    archive_schema_version: int = Field(ge=1)
    occurred_at: UtcInstant


class InspectBucketArchiveCommand(BaseModel):
    """Operator request to inspect a sealed bucket archive without restoring it.

    Read-only: the source archive is neither decrypted nor written to. This
    lets an operator confirm which bucket a backup file holds, when it was
    written, and whether it carries a recovery-wrap member, without needing
    the sealing key.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_path: Path


class InspectBucketArchiveResult(BaseModel):
    """Outcome of a successful sealed-archive inspection.

    Every field is read from the archive's plaintext header plus the
    on-disk file size; the AEAD-encrypted payload itself is never opened,
    so this result cannot report per-store row counts. ``manifest_digest``
    is the header's integrity anchor (unverified here — verification only
    happens during a real ``import``, where it is authenticated as AEAD
    associated data at decryption).
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    manifest_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    recovery_wrap_present: bool
    archive_schema_version: int = Field(ge=1)
    created_at: UtcInstant
    size_bytes: int = Field(ge=0)
