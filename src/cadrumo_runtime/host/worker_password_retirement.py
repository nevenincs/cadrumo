"""Validate a password-rotation successor without granting a replacement lease."""

from __future__ import annotations

from uuid import UUID

from cadrumo.application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    ProfilePassphraseRotationOperationRequest,
)
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome

from .worker_operation_binding import WorkerOperationBinding


def password_retirement_payload(
    identity: OperationIdentity, binding: WorkerOperationBinding | None
) -> ProfilePassphraseRotationOperationRequest | None:
    """Return only the payload of this exact rotation invocation."""
    if (
        binding is None
        or identity.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
        or binding.request.definition_id != identity.definition_id
        or binding.request.subject_ref != identity.subject_ref
        or not isinstance(binding.request.payload, ProfilePassphraseRotationOperationRequest)
    ):
        return None
    return binding.request.payload


def preserves_password_profile(
    payload: ProfilePassphraseRotationOperationRequest, outcome: ProfilePassphraseRotationOutcome, profile_id: UUID
) -> bool:
    """Require the original profile and a preserved DEK epoch."""
    return (
        payload.profile_id == profile_id
        and outcome.profile_id == str(payload.profile_id)
        and outcome.dek_epoch_preserved
    )
