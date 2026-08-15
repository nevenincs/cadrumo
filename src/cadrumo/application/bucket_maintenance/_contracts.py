"""Pydantic command + result records for :class:`BucketMaintenanceService`.

Used by: :mod:`~._service` to implement bucket operations.

The contract records sit at the package boundary so a programmatic
caller (the CLI handler, a future MCP surface) gets the same typed
input + output shape that the service consumes. Closed-value axes are
typed as their core enums per the architecture-boundaries discipline.
Every bucket selector is a :class:`BucketId`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, Hex64Str
from ...core.identity import BucketId, ContentDigest
from ...core.time import UtcInstant
from ...domain.retention import RetentionFloorAssessment
from ...domain.user_profile import ProfileSetupState
from .._bucket_deletion_contracts import BucketDeletionFingerprint


class AssessBucketDeletionCommand(BaseModel):
    """Read-only deletion-assessment intent for one explicit bucket."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId


class BucketDeletionAssessment(BaseModel):
    """Assessment of an explicit bucket target before deletion.

    The existing and absent forms are mutually exclusive. An existing
    assessment carries the bucket label, optional profile setup state,
    deletion fingerprint, and :class:`RetentionFloorAssessment`; an absent
    assessment carries none of those values.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    exists: bool
    label: str | None = Field(default=None, min_length=1, max_length=160)
    setup_state: ProfileSetupState | None = None
    fingerprint: BucketDeletionFingerprint | None = None
    retention: RetentionFloorAssessment | None = None

    @model_validator(mode="after")
    def _validate_existence_shape(self) -> BucketDeletionAssessment:
        present_fields = (self.label, self.fingerprint, self.retention)
        if self.exists and any(value is None for value in present_fields):
            raise ValueError("existing deletion assessment requires label, fingerprint, and retention")
        if not self.exists and any(value is not None for value in present_fields):
            raise ValueError("absent deletion assessment cannot carry bucket metadata")
        return self


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
    overwrite an existing target. The archive is sealed under the
    profile's own custody and carries committed profile data only; a
    profile's recovery record is an exclusive separate artifact with its
    own export grammar and is never folded into this transport.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    output_path: Path


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
    manifest_digest: ContentDigest
    occurred_at: UtcInstant


class ImportBucketCommand(BaseModel):
    """Operator request to import a sealed bucket archive.

    The ``source_path`` is operator-specified. The service refuses
    when the archive's ``bucket_id`` collides with an existing live
    profile unless ``force_replace`` is ``True``. Import is authorised
    by the profile's own password; it never discovers, requires, or
    falls back to recovery material.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_path: Path
    force_replace: bool = False


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
    manifest_digest: ContentDigest
    archive_schema_version: int = Field(ge=1)
    occurred_at: UtcInstant


class InspectBucketArchiveCommand(BaseModel):
    """Operator request to inspect a sealed bucket archive without restoring it.

    Read-only: the source archive is neither decrypted nor written to. This
    lets an operator confirm which bucket a backup file holds and when it was
    written, without needing the sealing key.
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
    manifest_digest: ContentDigest
    archive_schema_version: int = Field(ge=1)
    created_at: UtcInstant
    size_bytes: int = Field(ge=0)
