"""Record contracts for durable reset journals.

These models define local journal shapes and invariants only. They do not
implement reset orchestration, discovery, transition enforcement, resume, or
completion semantics.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG
from ..core.time import validate_utc_aware
from ..domain.user_profile import UserProfileStatus
from ._bucket_deletion_contracts import BucketDeletionFingerprint

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
CONFIG_RESET_SCHEMA_VERSION = 1


class ConfigResetOperationStatus(StrEnum):
    """Closed vocabulary of operation-status labels, without transition rules."""

    INCOMPLETE = "incomplete"
    PAUSED = "paused"
    COMPLETE = "complete"


class ConfigResetPauseReason(StrEnum):
    """Closed vocabulary of reasons that require an explicit resume."""

    RETENTION_UNRESOLVED = "retention_unresolved"
    TARGET_STATE_CHANGED = "target_state_changed"
    POINTER_CHANGED = "pointer_changed"


class ConfigResetTargetPhase(StrEnum):
    """Closed vocabulary of target-phase labels, without transition rules."""

    SNAPSHOTTED = "snapshotted"
    RETENTION_APPROVED = "retention_approved"
    AUTH_CLEARING = "auth_clearing"
    AUTH_CLEARED = "auth_cleared"
    POINTER_RECONCILING = "pointer_reconciling"
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
        self._validate_existence_correlation()
        self._validate_marker_phase()
        self._validate_completion_timestamp()
        return self

    def _validate_existence_correlation(self) -> None:
        if self.exists_at_snapshot != (self.fingerprint is not None):
            raise ValueError("existing reset target requires a deletion fingerprint")
        if self.exists_at_snapshot != (self.label is not None and self.status_at_snapshot is not None):
            raise ValueError("existing reset target requires label and lifecycle status")

    def _validate_marker_phase(self) -> None:
        if self.deletion_marker is not None and self.deletion_marker.bucket_id != self.bucket_id:
            raise ValueError("deletion marker bucket id does not match its reset target")
        if self.phase is ConfigResetTargetPhase.DELETING and self.deletion_marker is None:
            raise ValueError("deleting target requires exactly one deletion marker")
        if self.phase is ConfigResetTargetPhase.DELETED:
            if self.exists_at_snapshot != (self.deletion_marker is not None):
                raise ValueError("deleted existing target requires a marker; deleted absent target forbids one")
        elif self.deletion_marker is not None and self.phase is not ConfigResetTargetPhase.DELETING:
            raise ValueError("deletion marker is valid only for deleting/deleted targets")

    def _validate_completion_timestamp(self) -> None:
        if (self.phase is ConfigResetTargetPhase.DELETED) != (self.completed_at is not None):
            raise ValueError("deleted target requires exactly one completion timestamp")
        if self.completed_at is not None:
            validate_utc_aware(self.completed_at)


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

    Targets are unique and sorted. The model accepts only the current schema
    version and validates its own record structure. It does not enforce state
    transitions.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = CONFIG_RESET_SCHEMA_VERSION
    operation_id: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    status: ConfigResetOperationStatus = ConfigResetOperationStatus.INCOMPLETE
    started_at: datetime
    updated_at: datetime
    pointer_snapshot: ConfigResetPointerSnapshot
    targets: tuple[ConfigResetTarget, ...]
    pause_reason: ConfigResetPauseReason | None = None
    paused_target_ids: tuple[str, ...] = ()
    summary: ConfigResetSummary | None = None

    @model_validator(mode="after")
    def _validate_operation(self) -> ConfigResetOperation:
        self._validate_timestamps()
        self._validate_target_ordering()
        self._validate_completion()
        self._validate_pause()
        return self

    def _validate_timestamps(self) -> None:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("reset journal updated_at precedes started_at")

    def _validate_target_ordering(self) -> None:
        bucket_ids = tuple(target.bucket_id for target in self.targets)
        if bucket_ids != tuple(sorted(bucket_ids)) or len(bucket_ids) != len(set(bucket_ids)):
            raise ValueError("reset targets must be unique and sorted by bucket id")
        for target in self.targets:
            marker = target.deletion_marker
            if marker is not None and marker.operation_id != self.operation_id:
                raise ValueError("deletion marker operation id does not match its journal")

    def _validate_completion(self) -> None:
        if (self.status is ConfigResetOperationStatus.COMPLETE) != (self.summary is not None):
            raise ValueError("complete reset operation requires exactly one summary")
        if self.status is not ConfigResetOperationStatus.COMPLETE:
            return
        if any(target.phase is not ConfigResetTargetPhase.DELETED for target in self.targets):
            raise ValueError("complete reset operation requires every target to be deleted")
        assert self.summary is not None
        self._validate_summary_reconciliation(self.summary)

    def _expected_summary_counts(self) -> tuple[int, int, int]:
        expected_deleted_count = sum(target.exists_at_snapshot for target in self.targets)
        expected_already_absent_count = len(self.targets) - expected_deleted_count
        expected_override_count = sum(
            target.retention is not None and target.retention.override_approved for target in self.targets
        )
        return expected_deleted_count, expected_already_absent_count, expected_override_count

    def _validate_summary_reconciliation(self, summary: ConfigResetSummary) -> None:
        expected_deleted_count, expected_already_absent_count, expected_override_count = self._expected_summary_counts()
        if summary.target_count != len(self.targets):
            raise ValueError("complete reset summary target count does not match targets")
        if summary.deleted_count != expected_deleted_count:
            raise ValueError("complete reset summary deleted count does not match targets")
        if summary.already_absent_count != expected_already_absent_count:
            raise ValueError("complete reset summary absent count does not match targets")
        if summary.retention_override_count != expected_override_count:
            raise ValueError("complete reset summary retention override count does not match targets")
        if summary.completed_at != self.updated_at:
            raise ValueError("complete reset summary timestamp must match operation update timestamp")
        if any(target.completed_at is None or target.completed_at > summary.completed_at for target in self.targets):
            raise ValueError("complete reset target timestamps must precede operation completion")

    def _validate_pause(self) -> None:
        paused = self.status is ConfigResetOperationStatus.PAUSED
        if paused != (self.pause_reason is not None):
            raise ValueError("paused reset operation requires exactly one pause reason")
        if paused != bool(self.paused_target_ids):
            raise ValueError("paused reset operation requires one or more paused target ids")
        if self.paused_target_ids != tuple(sorted(set(self.paused_target_ids))):
            raise ValueError("paused reset target ids must be unique and sorted")
        bucket_ids = {target.bucket_id for target in self.targets}
        if any(bucket_id not in bucket_ids for bucket_id in self.paused_target_ids):
            raise ValueError("paused target ids must belong to the reset target set")


def new_config_reset_operation_id() -> str:
    """Generate a cryptographically random 256-bit operation identifier.

    Returns:
        A lowercase hexadecimal identifier.
    """
    return secrets.token_hex(32)


__all__ = [
    "CONFIG_RESET_SCHEMA_VERSION",
    "ConfigResetDeletionMarker",
    "ConfigResetOperation",
    "ConfigResetOperationStatus",
    "ConfigResetPauseReason",
    "ConfigResetPointerSnapshot",
    "ConfigResetRetentionDecision",
    "ConfigResetSummary",
    "ConfigResetTarget",
    "ConfigResetTargetPhase",
    "new_config_reset_operation_id",
]
