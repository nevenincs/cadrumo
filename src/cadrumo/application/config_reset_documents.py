"""The public document of a durable reset journal: what ``aeat config reset`` prints and what its acts reply.

The projection carries no fingerprint and no deletion witness. The runtime's
reset acts reply with this same document, so a command and an act print one
journal. The :class:`OutputSchema` declares the public response shape.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import NonNegativeInt, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hex import Hex64Str
from ..core.identity.bucket import BucketId
from ..core.identity.profile_label import ProfileLabel
from ..core.json_contract import OutputSchema
from ..core.time.utc import validate_utc_aware
from ..domain.user_profile.values import ProfileSetupState
from .config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetPauseReason,
    ConfigResetTargetPhase,
)


class ConfigResetTargetPayload(OutputSchema):
    """Secret-free phase projection for one reset target."""

    bucket_id: BucketId
    label: ProfileLabel | None = None
    setup_state_at_snapshot: ProfileSetupState | None = None
    exists_at_snapshot: bool
    phase: ConfigResetTargetPhase
    retention_blocks_erase: bool | None
    retention_override_approved: bool | None
    completed_at: str | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_completed_at(self) -> ConfigResetTargetPayload:
        if self.completed_at is not None:
            validate_utc_aware(datetime.fromisoformat(self.completed_at))
        return self


class ConfigResetSummaryPayload(OutputSchema):
    """Reconciled completion counts for one reset operation."""

    target_count: NonNegativeInt
    deleted_count: NonNegativeInt
    already_absent_count: NonNegativeInt
    retention_override_count: NonNegativeInt
    completed_at: str

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_summary(self) -> ConfigResetSummaryPayload:
        validate_utc_aware(datetime.fromisoformat(self.completed_at))
        if self.deleted_count + self.already_absent_count != self.target_count:
            raise ValueError("reset summary target counts do not reconcile")
        if self.retention_override_count > self.target_count:
            raise ValueError("retention override count cannot exceed target count")
        return self


class ConfigResetOperationPayload(OutputSchema):
    """Credential-free operator projection of one durable reset journal."""

    operation_id: Hex64Str
    status: ConfigResetOperationStatus
    started_at: str
    updated_at: str
    pause_reason: ConfigResetPauseReason | None
    paused_target_ids: list[str]
    targets: list[ConfigResetTargetPayload]
    summary: ConfigResetSummaryPayload | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_operation(self) -> ConfigResetOperationPayload:
        started_at = datetime.fromisoformat(self.started_at)
        updated_at = datetime.fromisoformat(self.updated_at)
        validate_utc_aware(started_at)
        validate_utc_aware(updated_at)
        if updated_at < started_at:
            raise ValueError("reset journal updated_at precedes started_at")
        paused = self.status is ConfigResetOperationStatus.PAUSED
        if paused != (self.pause_reason is not None):
            raise ValueError("paused reset operation requires exactly one pause reason")
        if paused != bool(self.paused_target_ids):
            raise ValueError("paused reset operation requires one or more paused target ids")
        if self.paused_target_ids != sorted(set(self.paused_target_ids)):
            raise ValueError("paused reset target ids must be unique and sorted")
        target_ids = {target.bucket_id for target in self.targets}
        if any(target_id not in target_ids for target_id in self.paused_target_ids):
            raise ValueError("paused target ids must belong to the reset target set")
        if (self.status is ConfigResetOperationStatus.COMPLETE) != (self.summary is not None):
            raise ValueError("complete reset operation requires exactly one summary")
        if self.status is ConfigResetOperationStatus.COMPLETE:
            self._validate_completion_reconciliation()
        return self

    def _validate_completion_reconciliation(self) -> None:
        summary = self._require_completion_summary()
        self._validate_completed_target_phases()
        expected_counts = self._expected_completion_counts()
        self._validate_completion_counts(summary, expected_counts)
        self._validate_completion_timestamp(summary)

    def _require_completion_summary(self) -> ConfigResetSummaryPayload:
        summary = self.summary
        if summary is None:
            raise ValueError("complete reset operation requires exactly one summary")
        return summary

    def _validate_completed_target_phases(self) -> None:
        if any(target.phase is not ConfigResetTargetPhase.DELETED for target in self.targets):
            raise ValueError("complete reset operation requires every target to be deleted")

    def _expected_completion_counts(self) -> tuple[int, int, int]:
        expected_deleted_count = sum(target.exists_at_snapshot for target in self.targets)
        expected_already_absent_count = len(self.targets) - expected_deleted_count
        expected_override_count = sum(bool(target.retention_override_approved) for target in self.targets)
        return expected_deleted_count, expected_already_absent_count, expected_override_count

    def _validate_completion_counts(
        self,
        summary: ConfigResetSummaryPayload,
        expected_counts: tuple[int, int, int],
    ) -> None:
        expected_deleted_count, expected_already_absent_count, expected_override_count = expected_counts
        if summary.target_count != len(self.targets):
            raise ValueError("complete reset summary target count does not match targets")
        if summary.deleted_count != expected_deleted_count:
            raise ValueError("complete reset summary deleted count does not match targets")
        if summary.already_absent_count != expected_already_absent_count:
            raise ValueError("complete reset summary absent count does not match targets")
        if summary.retention_override_count != expected_override_count:
            raise ValueError("complete reset summary retention override count does not match targets")

    def _validate_completion_timestamp(self, summary: ConfigResetSummaryPayload) -> None:
        if summary.completed_at != self.updated_at:
            raise ValueError("complete reset summary timestamp must match operation update timestamp")

    @classmethod
    def from_operation(cls, operation: ConfigResetOperation) -> ConfigResetOperationPayload:
        """Project the application journal without fingerprints or deletion witnesses."""
        targets = [
            ConfigResetTargetPayload(
                bucket_id=target.bucket_id,
                label=target.label,
                setup_state_at_snapshot=target.setup_state_at_snapshot,
                exists_at_snapshot=target.exists_at_snapshot,
                phase=target.phase,
                retention_blocks_erase=(target.retention.blocks_erase if target.retention is not None else None),
                retention_override_approved=(
                    target.retention.override_approved if target.retention is not None else None
                ),
                completed_at=(target.completed_at.isoformat() if target.completed_at is not None else None),
            )
            for target in operation.targets
        ]
        summary = operation.summary
        return cls(
            operation_id=operation.operation_id,
            status=operation.status,
            started_at=operation.started_at.isoformat(),
            updated_at=operation.updated_at.isoformat(),
            pause_reason=operation.pause_reason,
            paused_target_ids=list(operation.paused_target_ids),
            targets=targets,
            summary=(
                ConfigResetSummaryPayload(
                    target_count=summary.target_count,
                    deleted_count=summary.deleted_count,
                    already_absent_count=summary.already_absent_count,
                    retention_override_count=summary.retention_override_count,
                    completed_at=summary.completed_at.isoformat(),
                )
                if summary is not None
                else None
            ),
        )
