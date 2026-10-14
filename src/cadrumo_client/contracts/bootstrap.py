"""Exact bootstrap custody requests; credentials travel only in secret frames."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, model_validator

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.prospective_password import ProspectiveProfilePasswordRefusal
from cadrumo.application.user_profile.recovery_custody import ProfilePassphraseResetOutcome
from cadrumo.core.identity.digest import PrefixedContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .automation_lifecycle import HumanSignInRevocationResult


class PasswordResetPrepare(BaseModel):
    """Pin the exact existing password envelope without admitting a session."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["password_reset_prepare"] = "password_reset_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection


class PasswordReset(BaseModel):
    """Replace one prepared predecessor after separate recovery-code proof."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["password_reset"] = "password_reset"
    request_id: UUID
    profile_id: UUID
    envelope_digest: PrefixedContentDigest


class PasswordResetSecrets(BaseModel):
    """Secret-frame-only payload, excluded from the ordinary request union."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    recovery_code: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


class _BootstrapReply(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID


class PasswordResetPrepared(_BootstrapReply):
    """Nonsecret predecessor identity, never authority to perform a reset."""

    kind: Literal["password_reset_prepared"] = "password_reset_prepared"
    envelope_digest: PrefixedContentDigest


class PasswordResetCompleted(_BootstrapReply):
    """Committed password change and separate truthful receipt cleanup facts."""

    kind: Literal["password_reset_completed"] = "password_reset_completed"
    outcome: ProfilePassphraseResetOutcome
    human_sign_in_revocation: HumanSignInRevocationResult


class PasswordResetRefused(_BootstrapReply):
    """Allowlisted proof/policy refusal without input text or key material."""

    kind: Literal["password_reset_refused"] = "password_reset_refused"
    code: Literal[
        "recovery_code_rejected",
        "recovery_not_enrolled",
        "passphrase_confirmation_mismatch",
        "invalid_password",
        "throttled",
    ]
    remaining_seconds: int | None = Field(default=None, ge=0)
    password_refusal: ProspectiveProfilePasswordRefusal | None = None

    @model_validator(mode="after")
    def _refusal_facts(self) -> PasswordResetRefused:
        if (self.code == "throttled") != (self.remaining_seconds is not None):
            raise ValueError("remaining time must belong to a throttling refusal")
        if (self.code == "invalid_password") != (self.password_refusal is not None):
            raise ValueError("password facts must belong to an invalid-password refusal")
        return self
