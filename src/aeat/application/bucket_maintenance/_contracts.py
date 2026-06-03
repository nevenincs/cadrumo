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
