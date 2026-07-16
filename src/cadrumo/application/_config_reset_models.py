"""Record contracts for durable reset journals.

These models define local journal shapes and invariants only. They do not
implement reset orchestration, discovery, transition enforcement, resume, or
completion semantics.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG
from ..core.time import validate_utc_aware
from ..domain.user_profile import UserProfileStatus
from ._bucket_deletion_contracts import BucketDeletionFingerprint

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ConfigResetOperationStatus(StrEnum):
    """Closed vocabulary of operation-status labels, without transition rules."""

    INCOMPLETE = "incomplete"
    PAUSED = "paused"
    COMPLETE = "complete"


class ConfigResetTargetPhase(StrEnum):
    """Closed vocabulary of target-phase labels, without transition rules."""

    SNAPSHOTTED = "snapshotted"
    RETENTION_APPROVED = "retention_approved"
    AUTH_CLEARED = "auth_cleared"
    POINTER_RECONCILED = "pointer_reconciled"
    DELETING = "deleting"
    DELETED = "deleted"


class ConfigResetPointerSnapshot(BaseModel):
    """Snapshot correlating pointer presence, bucket identity, and content hash."""

    model_config = STRICT_FROZEN_CONFIG

    present: bool
    bucket_id: str | None = Field(default=None, min_length=1)
    content_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )

    @model_validator(mode="after")
    def _validate_presence(self) -> ConfigResetPointerSnapshot:
        if self.present != (self.bucket_id is not None and self.content_sha256 is not None):
            raise ValueError("pointer snapshot presence must match bucket id and content digest")
        return self


class ConfigResetRetentionDecision(BaseModel):
    """Journaled correlations supporting a retention decision.

    The record enforces internal count, flag, and reason correlations only; it
    is not proof of external policy approval.
    """

    model_config = STRICT_FROZEN_CONFIG

    assessed_at: datetime
    blocks_erase: bool
    retained_record_count: int = Field(ge=0)
    latest_safe_erase_date: datetime | None = None
    override_approved: bool = False
    override_reason: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def _validate_decision(self) -> ConfigResetRetentionDecision:
        validate_utc_aware(self.assessed_at)
        if self.latest_safe_erase_date is not None:
            validate_utc_aware(self.latest_safe_erase_date)
        if self.blocks_erase != (self.retained_record_count > 0):
            raise ValueError("retention blocking flag must match retained record count")
        if self.override_approved != (self.override_reason is not None):
            raise ValueError("retention override approval requires exactly one non-empty reason")
        if self.override_approved and not self.blocks_erase:
            raise ValueError("retention override cannot be approved when no record blocks erase")
        return self


class ConfigResetDeletionMarker(BaseModel):
    """Ownership-witness shape intended for pre-delete persistence.

    This model does not implement the orchestration that writes the marker.
    """

    model_config = STRICT_FROZEN_CONFIG

    operation_id: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    bucket_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    marked_at: datetime

    @model_validator(mode="after")
    def _validate_marked_at(self) -> ConfigResetDeletionMarker:
        validate_utc_aware(self.marked_at)
        return self


class ConfigResetTarget(BaseModel):
    """Explicit bucket target recorded in a reset journal.

    The model represents a supplied target and does not perform discovery.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str = Field(min_length=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    status_at_snapshot: UserProfileStatus | None = None
    exists_at_snapshot: bool
    fingerprint: BucketDeletionFingerprint | None = None
    phase: ConfigResetTargetPhase = ConfigResetTargetPhase.SNAPSHOTTED
    retention: ConfigResetRetentionDecision | None = None
    deletion_marker: ConfigResetDeletionMarker | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_target_state(self) -> ConfigResetTarget:
        if self.exists_at_snapshot != (self.fingerprint is not None):
            raise ValueError("existing reset target requires a deletion fingerprint")
        if self.exists_at_snapshot != (self.label is not None and self.status_at_snapshot is not None):
            raise ValueError("existing reset target requires label and lifecycle status")
        if self.deletion_marker is not None and self.deletion_marker.bucket_id != self.bucket_id:
            raise ValueError("deletion marker bucket id does not match its reset target")
        deleting = self.phase in {ConfigResetTargetPhase.DELETING, ConfigResetTargetPhase.DELETED}
        if deleting != (self.deletion_marker is not None):
            raise ValueError("deleting/deleted target requires exactly one deletion marker")
        if (self.phase is ConfigResetTargetPhase.DELETED) != (self.completed_at is not None):
            raise ValueError("deleted target requires exactly one completion timestamp")
        if self.completed_at is not None:
            validate_utc_aware(self.completed_at)
        return self


class ConfigResetSummary(BaseModel):
    """Reconciled-count shape for a completed operation record.

    The model defines the record shape but is not itself reset orchestration.
    """

    model_config = STRICT_FROZEN_CONFIG

    target_count: int = Field(ge=0)
    deleted_count: int = Field(ge=0)
    already_absent_count: int = Field(ge=0)
    retention_override_count: int = Field(ge=0)
    completed_at: datetime

    @model_validator(mode="after")
    def _validate_summary(self) -> ConfigResetSummary:
        validate_utc_aware(self.completed_at)
        if self.deleted_count + self.already_absent_count != self.target_count:
            raise ValueError("reset summary target counts do not reconcile")
        if self.retention_override_count > self.target_count:
            raise ValueError("retention override count cannot exceed target count")
        return self


class ConfigResetOperation(BaseModel):
    """Credential-free reset-journal document with local invariants.

    Targets are unique and sorted. The model accepts schema versions greater
    than or equal to one and validates its own record structure. It does not
    enforce state transitions or fully reconcile phase, status, target, and
    summary semantics.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=1, ge=1)
    operation_id: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    status: ConfigResetOperationStatus = ConfigResetOperationStatus.INCOMPLETE
    started_at: datetime
    updated_at: datetime
    pointer_snapshot: ConfigResetPointerSnapshot
    targets: tuple[ConfigResetTarget, ...]
    summary: ConfigResetSummary | None = None

    @model_validator(mode="after")
    def _validate_operation(self) -> ConfigResetOperation:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("reset journal updated_at precedes started_at")
        bucket_ids = tuple(target.bucket_id for target in self.targets)
        if bucket_ids != tuple(sorted(bucket_ids)) or len(bucket_ids) != len(set(bucket_ids)):
            raise ValueError("reset targets must be unique and sorted by bucket id")
        for target in self.targets:
            marker = target.deletion_marker
            if marker is not None and marker.operation_id != self.operation_id:
                raise ValueError("deletion marker operation id does not match its journal")
        if (self.status is ConfigResetOperationStatus.COMPLETE) != (self.summary is not None):
            raise ValueError("complete reset operation requires exactly one summary")
        return self


def new_config_reset_operation_id() -> str:
    """Generate a cryptographically random 256-bit operation identifier.

    Returns:
        A lowercase hexadecimal identifier.
    """
    return secrets.token_hex(32)


__all__ = [
    "ConfigResetDeletionMarker",
    "ConfigResetOperation",
    "ConfigResetOperationStatus",
    "ConfigResetPointerSnapshot",
    "ConfigResetRetentionDecision",
    "ConfigResetSummary",
    "ConfigResetTarget",
    "ConfigResetTargetPhase",
    "new_config_reset_operation_id",
]
