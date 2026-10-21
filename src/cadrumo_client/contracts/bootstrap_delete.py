"""Confirmed single-profile custody deletion, without session authority."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionReceipt,
)
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class ProfileDeletePrepare(BaseModel):
    """Confirm the exact content observed by the non-mutating preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["profile_delete_prepare"] = "profile_delete_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    fingerprint: BucketDeletionFingerprint


class ProfileDelete(BaseModel):
    """Execute or resume an existing journal's exact single-target confirmation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["profile_delete"] = "profile_delete"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    confirmation: ProfileCustodyDeleteConfirmation

    @model_validator(mode="after")
    def _target(self) -> ProfileDelete:
        if self.confirmation.profile_id != self.profile_id:
            raise ValueError("deletion confirmation must name the exact target")
        return self


class ProfileDeletePrepared(BaseModel):
    """Existing journal coordinates, not a portable authentication bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_delete_prepared"] = "profile_delete_prepared"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    confirmation: ProfileCustodyDeleteConfirmation


class ProfileDeleted(BaseModel):
    """Return only the existing custody owner's durable completion evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_deleted"] = "profile_deleted"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    receipt: ProfileCustodyTransactionReceipt


class ProfileDeleteRefused(BaseModel):
    """A bounded refusal that never substitutes revocation for completed deletion."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_delete_refused"] = "profile_delete_refused"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    code: Literal["selected_profile", "custody_changed", "custody_refused", "cleanup_incomplete"]
    transaction_id: UUID | None = None
