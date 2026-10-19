"""Nonsecret sign-in outcomes and refusals shared by the runtime and every frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.identity.bucket import BucketId
from cadrumo.core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.profile_session import KeychainUnavailability, ProfileSessionRefusalReason, ReceiptBindingRefusal
from cadrumo.domain.user_profile.errors import UserProfileError


class SignInRefusal(BaseModel):
    """Preserve receipt provenance, throttling and a rejected password without diagnostic strings.

    ``credential_rejected`` means the presented password did not prove the
    profile; the failed attempt has been counted by the throttle.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    reason: ProfileSessionRefusalReason | Literal["throttled", "credential_rejected"]
    binding: ReceiptBindingRefusal | None = None
    remaining_seconds: int | None = Field(default=None, ge=0)
    keychain: KeychainUnavailability | None = None
    """Why the refused process cannot use the keychain holding sign-in proof, when it cannot."""

    @model_validator(mode="after")
    def _throttle_time(self) -> SignInRefusal:
        if (self.reason == "throttled") != (self.remaining_seconds is not None):
            raise ValueError("remaining time is required exactly for throttling")
        return self


class ProfileLoginOutcome(BaseModel):
    """Typed result of one sign-in.

    Carries no key material: the unlocked key stays with its runtime-owned
    custody, never with this record.

    Attributes:
        bucket_id: Immutable UUID identity of the authenticated profile.
        label: Operator-facing display label of that profile.
        authenticated_at: UTC instant the session was established. On an
            idempotent no-op this is the ORIGINAL login instant, never
            re-stamped.
        idle_deadline: Current sliding idle deadline.
        absolute_deadline: Immutable absolute session cap.
        session_persisted: ``False`` when the host has no usable OS
            keychain, or the login ran in-process with no runtime-observed
            OS login to bind, so the session is process-scoped only.
        already_authenticated: ``True`` when a still-valid persisted
            session was resumed as a no-op (no re-prompt, no new record).
        closed_previous_bucket_id: The profile whose sign-in this login
            ended, or ``None``. The candidate and invocation authentication
            doors retire no other profile's sign-in themselves and leave it
            ``None``; the runtime does, when it admits a person's password
            sign-in to a profile, because one profile is signed in at a time,
            and the command that asked for that sign-in reports it here.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    already_authenticated: bool
    closed_previous_bucket_id: BucketId | None = None


class ProfileLoginThrottledError(UserProfileError):
    """Refuse a login attempt while the failed-attempt backoff is in force.

    Raised BEFORE any Argon2id derivation runs, so a caller hammering
    passphrases cannot use the key-derivation function as a timing
    oracle. The remaining wait rides in ``context`` so a frontend can render
    it without re-parsing the message.
    """

    def __init__(self, *, remaining_seconds: int) -> None:
        """Initialise the refusal with the operator's remaining wait."""
        super().__init__(
            translated_message="errors.refused.refused_profile_login_throttled",
            context={"seconds": str(remaining_seconds)},
        )
        self.remaining_seconds = remaining_seconds


class ProfileReceiptRefusedError(CadrumoError):
    """A human receipt did not prove the exact current capsule and deadline."""

    def __init__(
        self,
        reason: ProfileSessionRefusalReason,
        *,
        binding: ReceiptBindingRefusal | None = None,
        keychain: KeychainUnavailability | None = None,
    ) -> None:
        """Preserve the core refusal, and why the keychain could not be used, without receipt material."""
        self.reason = reason
        self.binding = binding
        self.keychain = keychain
        super().__init__(reason.value)
