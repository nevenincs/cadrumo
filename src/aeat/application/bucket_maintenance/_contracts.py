"""Pydantic command + result records for :class:`BucketMaintenanceService`.

Used by: :mod:`~._service` to implement bucket operations.

The contract records sit at the package boundary so a programmatic
caller (the CLI handler, a future MCP surface) gets the same typed
input + output shape that the service consumes. Closed-value axes are
typed as their core enums per the architecture-boundaries discipline.
Every bucket selector is a :class:`BucketId`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId


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
    occurred_at: datetime


class DeleteBucketCommand(BaseModel):
    """Operator request to destructively erase a bucket.

    ``confirmed=True`` is required at the service boundary so a
    programmatic caller observes the same guarantee the CLI ``--yes``
    flag provides. The active bucket cannot be deleted; the operator
    must switch profiles first.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    confirmed: bool = False


class DeleteBucketResult(BaseModel):
    """Outcome of a successful bucket erasure.

    Carries the deleted bucket's prior label so the operator-facing
    emitter can render a confirming line without re-reading anything.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    previous_label: str = Field(min_length=1, max_length=160)
    occurred_at: datetime


class BrowseBucketCommand(BaseModel):
    """Operator request to enumerate a bucket's namespace inventory.

    The current shape is namespace-level only: it returns each
    namespace and its row count without decrypting payloads. Key-level
    browse requires decryption and a ``SensitivityClass`` redaction
    policy, both deferred to a follow-up Step under the
    composition-pattern ADR.
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
    occurred_at: datetime


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
    occurred_at: datetime
