"""Pydantic command + result records for ``BucketMaintenanceService``.

The contract records sit at the package boundary so a programmatic
caller (the CLI handler, a future MCP surface) gets the same typed
input + output shape that the service consumes. Closed-value axes are
typed as their core enums per the architecture-boundaries discipline.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ...core.identity import BucketId


class RenameBucketCommand(BaseModel):
    """Operator request to relabel a bucket.

    Bucket identity is the stable UUID; only the operator-visible label
    moves. The service forwards the relabel to the profile-rename
    single-writer primitive, which holds the cross-store atomicity
    (encrypted record ``display_name`` and plaintext manifest ``label``
    move together).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
    new_label: str = Field(min_length=1, max_length=160)


class RenameBucketResult(BaseModel):
    """Outcome of a successful rename.

    Carries the prior label so the operator-facing emitter can render
    the before / after pair without re-reading the manifest. The
    ``occurred_at`` instant is the same instant carried by the
    ``BUCKET_RENAMED`` bucket event.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
    confirmed: bool = False


class DeleteBucketResult(BaseModel):
    """Outcome of a successful bucket erasure.

    Carries the deleted bucket's prior label so the operator-facing
    emitter can render a confirming line without re-reading anything.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
    namespace_filter: str | None = Field(default=None, min_length=1, max_length=128)


class BucketNamespaceInventoryRow(BaseModel):
    """One row of the namespace-inventory browse result."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    row_count: int = Field(ge=0)


class BrowseBucketResult(BaseModel):
    """Namespace-level browse outcome.

    Returns one row per namespace present in the bucket (optionally
    substring-filtered by ``namespace_filter``), each carrying the
    stored-row count. Read-only; emits no bucket event.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
    rows: tuple[BucketNamespaceInventoryRow, ...]
