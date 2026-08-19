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

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
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
