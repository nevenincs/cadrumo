"""Access outcomes that cross the wire: the closed denial codes, the allowed and denied decisions, and the status reply.

Each carries only allowlisted facts, never client input, exception text or a credential.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.time.utc import UtcInstant

from .access_vocabulary import AuthorityState, Availability, EffectiveScopeSummary
from .sign_in_outcomes import SignInRefusal


class AccessDenialCode(StrEnum):
    """Safe refusal facts, with no client input or exception text."""

    AUTHENTICATION_REQUIRED = "authentication_required"
    PROFILE_MISMATCH = "profile_mismatch"
    CUSTODY_CHANGED = "custody_changed"
    PROFILE_LOCKED = "profile_locked"
    AUTOMATION_SUSPENDED = "automation_suspended"
    SESSION_INACTIVE = "session_inactive"
    SESSION_EXPIRED = "session_expired"
    CONNECTION_MISMATCH = "connection_mismatch"
    CLIENT_MISMATCH = "client_mismatch"
    RUNTIME_CHANGED = "runtime_changed"
    CLOCK_INVALID = "clock_invalid"
    PARENT_INVALID = "parent_invalid"
    PRIVILEGE_EXPANSION = "privilege_expansion"
    GRANT_INACTIVE = "grant_inactive"
    GRANT_EXPIRED = "grant_expired"
    KEY_INACTIVE = "key_inactive"
    KEY_EXPIRED = "key_expired"
    OS_SESSION_UNAVAILABLE = "os_session_unavailable"
    OS_LOCKED = "os_locked"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    CUSTODY_UNAVAILABLE = "custody_unavailable"
    OPERATION_UNAVAILABLE = "operation_unavailable"
    SUBJECT_BUSY = "subject_busy"
    """An earlier operation of the same definition on the same subject has not settled."""
    FRONTEND_DENIED = "frontend_denied"
    OPERATION_DENIED = "operation_denied"
    DISCLOSURE_DENIED = "disclosure_denied"
    PERIOD_DENIED = "period_denied"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    PROVIDER_REQUIRED = "provider_required"
    RESPONSE_AUTHORITY_REQUIRED = "response_authority_required"
    REVIEW_ALREADY_CLAIMED = "review_already_claimed"
    REVIEW_CLAIM_STALE = "review_claim_stale"
    TRANSACTION_AUTHORITY_REQUIRED = "transaction_authority_required"
    HUMAN_AUTHORITY_REQUIRED = "human_authority_required"
    FRESH_PASSWORD_REQUIRED = "fresh_password_required"  # noqa: S105 -- public refusal code.
    ADMINISTRATION_DENIED = "administration_denied"
    PERSON_ACT_REQUIRED = "person_act_required"
    """The act is the person's own in Cadrumo: signing in, sessions, keys, secrets or work outside the profile."""


class AccessDenied(BaseModel):
    """A typed refusal; existing operator actions supply frontend recovery routes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["denied"] = "denied"
    code: AccessDenialCode
    sign_in: SignInRefusal | None = None


class AccessAllowed(BaseModel):
    """Point-in-time policy result, not a credential or an execution capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["allowed"] = "allowed"
    profile_id: UUID
    session_id: UUID
    expires_at: UtcInstant


type AccessDecision = Annotated[AccessAllowed | AccessDenied, Field(discriminator="outcome")]


class OperationResponseScopeAllowed(BaseModel):
    """Current profile permission only; the response owner still must prove its bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["response_scope_allowed"] = "response_scope_allowed"
    profile_id: UUID
    session_id: UUID
    expires_at: UtcInstant


class ProfileAccessStatus(BaseModel):
    """Non-secret independent status axes; never a cached logged-in authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    connected: bool
    credential_authenticated: bool
    profile_id: UUID | None
    session_id: UUID | None
    session_expires_at: UtcInstant | None
    grant_state: AuthorityState | None
    grant_expires_at: UtcInstant | None
    grant_valid: bool
    profile_bound: bool
    storage: Availability
    automation_custody: Availability
    published_authority: Availability
    provider: Availability
    effective_scope: EffectiveScopeSummary
    denial: AccessDenialCode | None
    human_resume_refusal: ProfileSessionRefusalReason | None = None
