"""Explicit policy requirements for profile-access administration.

These declarations do not enroll executors. Administration must enter the existing
operation services when implemented. Fresh proof is an owner-verified, exact-request
fact from secret submission, never a password field or a client assertion. The
lifecycle transaction consumes it once under its denial fence before any effect.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from .access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
)
from .session_authority_policy import evaluate_session_authority


class AccessAdministrationAction(StrEnum):
    """Intent vocabulary, separate from operation and recovery-action identities."""

    ENROLL = "enroll"
    APPROVE = "approve"
    DECLINE = "decline"
    INSPECT = "inspect"
    ROTATE = "rotate"
    RENEW = "renew"
    CHANGE_SCOPE = "change_scope"
    REVOKE_KEY = "revoke_key"
    REVOKE_GRANT = "revoke_grant"
    REVOKE_ALL_AUTOMATION = "revoke_all_automation"
    LOCK_SESSION = "lock_session"
    LOCK_PROFILE = "lock_profile"
    RESUME_PROFILE = "resume_profile"
    MANAGE_RUNTIME = "manage_runtime"


class AdministrationRequirement(StrEnum):
    """Capability floor, independent of CLI, TUI or MCP presentation."""

    OWN_SESSION = "own_session"
    HUMAN_PROFILE = "human_profile"
    FRESH_PASSWORD = "fresh_password"  # noqa: S105 -- public capability code, not a credential.
    LOCAL_RUNTIME_OWNER = "local_runtime_owner"


def administration_requirement(action: AccessAdministrationAction) -> AdministrationRequirement:
    """Return the explicit floor; ordinary keys cannot administer root authority."""
    if action is AccessAdministrationAction.LOCK_SESSION:
        return AdministrationRequirement.OWN_SESSION
    if action is AccessAdministrationAction.MANAGE_RUNTIME:
        return AdministrationRequirement.LOCAL_RUNTIME_OWNER
    if action in {
        AccessAdministrationAction.ENROLL,
        AccessAdministrationAction.APPROVE,
        AccessAdministrationAction.ROTATE,
        AccessAdministrationAction.RENEW,
        AccessAdministrationAction.CHANGE_SCOPE,
        AccessAdministrationAction.RESUME_PROFILE,
    }:
        return AdministrationRequirement.FRESH_PASSWORD
    return AdministrationRequirement.HUMAN_PROFILE


class AccessAdministrationRequest(BaseModel):
    """Identity of the exact reviewed request, including targets and proposed scope.

    The application computes ``request_digest`` from its credential-free typed
    operand, including target key/grant, destination, expiry and selected grants.
    Neither an arbitrary caller digest nor an old login outcome proves consent.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    profile_id: UUID
    action: AccessAdministrationAction
    request_digest: ContentDigest
    target_session_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> AccessAdministrationRequest:
        if (self.action is AccessAdministrationAction.LOCK_SESSION) != (self.target_session_id is not None):
            raise ValueError("session lock requires exactly one session target")
        return self


class FreshPasswordAuthorization(BaseModel):
    """Verified exact-request proof metadata; not a reusable authentication token."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request: AccessAdministrationRequest
    binding: ProfileAccessBinding
    profile_lock_generation: Annotated[int, Field(ge=0)]
    runtime_boot_id: UUID
    connection_id: UUID
    client_id: UUID
    originating_login_id: str
    verified_at: UtcInstant
    expires_at: UtcInstant
    verified_monotonic: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    consumed: bool

    @model_validator(mode="after")
    def _validate_proof(self) -> FreshPasswordAuthorization:
        duration = self.expires_at - self.verified_at
        if duration.total_seconds() <= 0 or duration > ACCESS_LEASE_MAXIMUM:
            raise ValueError("fresh password proof must expire within five minutes")
        if self.request.profile_id != self.binding.profile_id:
            raise ValueError("password proof must bind the exact profile")
        return self


class AdministrationAllowed(BaseModel):
    """Permission for one administration request; never an admitted session."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["allowed"] = "allowed"
    request_id: UUID
    expires_at: UtcInstant


type AdministrationDecision = Annotated[AdministrationAllowed | AccessDenied, Field(discriminator="outcome")]


def evaluate_access_administration(
    *,
    request: AccessAdministrationRequest,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
    password_proof: FreshPasswordAuthorization | None = None,
) -> AdministrationDecision:
    """Evaluate policy only; freshness consumption and lifecycle effects are separate.

    Profile-wide resume may use fresh password proof without a surviving session.
    Runtime administration requires its distinct OS-owner boundary and is never
    granted by profile authentication. Scope changes conservatively require fresh
    proof even when the requested change only narrows access.
    """
    if request.profile_id != profile.binding.profile_id:
        return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
    requirement = administration_requirement(request.action)
    if requirement is AdministrationRequirement.LOCAL_RUNTIME_OWNER:
        return AccessDenied(code=AccessDenialCode.ADMINISTRATION_DENIED)
    if requirement is AdministrationRequirement.FRESH_PASSWORD:
        return _evaluate_fresh_password_administration(request, password_proof, profile, context)
    return _evaluate_session_administration(request, session, ancestors, grant, key, profile, context, requirement)


def _evaluate_fresh_password_administration(
    request: AccessAdministrationRequest,
    proof: FreshPasswordAuthorization | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AdministrationDecision:
    if not _proof_matches(request, proof, profile, context) or proof is None:
        return AccessDenied(code=AccessDenialCode.FRESH_PASSWORD_REQUIRED)
    # A restricted frontend must perform the separate password journey. This
    # result identifies that proof request, never upgrades its API session.
    if profile.globally_locked and request.action is not AccessAdministrationAction.RESUME_PROFILE:
        return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
    return AdministrationAllowed(request_id=request.request_id, expires_at=proof.expires_at)


def _evaluate_session_administration(
    request: AccessAdministrationRequest,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
    requirement: AdministrationRequirement,
) -> AdministrationDecision:
    decision = evaluate_session_authority(
        session=session,
        ancestors=ancestors,
        grant=grant,
        key=key,
        profile=profile,
        context=context,
    )
    if isinstance(decision, AccessDenied):
        return decision
    if session is None:
        return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
    if requirement is AdministrationRequirement.OWN_SESSION and request.target_session_id == session.session_id:
        return AdministrationAllowed(request_id=request.request_id, expires_at=decision.expires_at)
    if session.kind is not SessionKind.HUMAN:
        return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    return AdministrationAllowed(request_id=request.request_id, expires_at=decision.expires_at)


def _proof_matches(
    request: AccessAdministrationRequest,
    proof: FreshPasswordAuthorization | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> bool:
    if proof is None or proof.consumed or context.clock_rollback_detected or not context.private_work_available:
        return False
    return (
        _proof_matches_reviewed_origin(request, proof, profile, context)
        and _proof_matches_current_authority(proof, profile, context)
        and _proof_is_within_lifetime(proof, context)
    )


def _proof_matches_reviewed_origin(
    request: AccessAdministrationRequest,
    proof: FreshPasswordAuthorization,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> bool:
    return proof.request == request and any(
        login.login_id == proof.originating_login_id
        and login.os_owner_id == profile.binding.os_owner_id
        and login.active
        and login.unlocked
        for login in context.login_contexts
    )


def _proof_matches_current_authority(
    proof: FreshPasswordAuthorization, profile: ProfileAccessState, context: AccessEvaluationContext
) -> bool:
    return (
        proof.binding == profile.binding
        and proof.profile_lock_generation == profile.lock_generation
        and proof.runtime_boot_id == context.runtime_boot_id
        and proof.connection_id == context.connection_id
        and proof.client_id == context.authenticated_client_id
    )


def _proof_is_within_lifetime(proof: FreshPasswordAuthorization, context: AccessEvaluationContext) -> bool:
    return (
        proof.verified_at <= context.now < proof.expires_at
        and 0
        <= context.monotonic_now - proof.verified_monotonic
        < (proof.expires_at - proof.verified_at).total_seconds()
    )
